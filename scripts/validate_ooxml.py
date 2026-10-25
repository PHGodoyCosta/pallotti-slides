"""Structural validation of a generated .pptx (OOXML package).

Checks: valid zip; ``[Content_Types].xml`` present and covering every part; every XML part
well formed; every internal relationship points to an existing part; no orphan part (every
part reachable from ``_rels/.rels``); unique slide ids in ``p:sldIdLst`` pointing to slide
relationships; no ``{{tag}}`` or ``@pallotti`` left (unless ``--allow-tags``); the file opens
in python-pptx.

Usage: uv run python scripts/validate_ooxml.py deck.pptx [more.pptx ...] [--allow-tags]
Exit code 1 when any file has problems.
"""

import posixpath
import re
import sys
import zipfile
from collections import deque
from pathlib import Path

from lxml import etree

CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SLIDE_REL = f"{R_NS}/slide"
CONTENT_TYPES = "[Content_Types].xml"
_LEFTOVER = re.compile(rb"\{\{|@pallotti")
MAX_PRINTED = 30


def _rels_name(part: str) -> str:
    directory, name = posixpath.split(part)
    return posixpath.join(directory, "_rels", f"{name}.rels")


def _source_of(rels: str) -> str:
    directory, name = posixpath.split(rels)
    return posixpath.join(posixpath.dirname(directory), name.removesuffix(".rels"))


def _resolve(source: str, target: str) -> str:
    """Part name (without the leading ``/``) of ``target`` relative to part ``source``."""
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target)).lstrip("/")


def _extension(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in posixpath.basename(name) else ""


def validate(path: Path, *, allow_tags: bool = False) -> list[str]:
    """Problems found in ``path`` (empty list = valid)."""
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as error:
        return [f"not a zip file: {error}"]
    problems: list[str] = []
    with archive:
        bad = archive.testzip()
        if bad is not None:
            problems.append(f"corrupted zip member: {bad}")
        names = [n for n in archive.namelist() if not n.endswith("/")]
        name_set = set(names)
        if len(names) != len(name_set):
            problems.append("duplicated zip members")

        # Well-formed XML.
        trees: dict[str, etree._Element] = {}
        for name in names:
            if name.endswith((".xml", ".rels")):
                try:
                    trees[name] = etree.fromstring(archive.read(name))
                except etree.XMLSyntaxError as error:
                    problems.append(f"malformed XML in {name}: {error}")

        # Content types.
        types = trees.get(CONTENT_TYPES)
        if types is None:
            return [*problems, f"missing {CONTENT_TYPES}"]
        defaults = {e.get("Extension", "").lower() for e in types.iter(f"{{{CT_NS}}}Default")}
        overrides = {
            (e.get("PartName") or "").lstrip("/") for e in types.iter(f"{{{CT_NS}}}Override")
        }
        for override in sorted(overrides - name_set):
            problems.append(f"content type override for a missing part: /{override}")
        for name in names:
            if name == CONTENT_TYPES:
                continue
            if name not in overrides and _extension(name) not in defaults:
                problems.append(f"part without content type: {name}")

        # Relationships: targets exist; collect the graph.
        edges: dict[str, list[str]] = {}
        slide_targets: dict[str, str] = {}
        for name, tree in trees.items():
            if not name.endswith(".rels"):
                continue
            source = "" if name == "_rels/.rels" else _source_of(name)
            if source and source not in name_set:
                problems.append(f"relationships of a missing part: {name}")
            ids: set[str] = set()
            for rel in tree.iter(f"{{{REL_NS}}}Relationship"):
                rel_id = rel.get("Id", "")
                if rel_id in ids:
                    problems.append(f"duplicated relationship id {rel_id} in {name}")
                ids.add(rel_id)
                if rel.get("TargetMode") == "External":
                    continue
                target = _resolve(source, rel.get("Target", ""))
                if target not in name_set:
                    problems.append(f"{name}: {rel_id} points to missing part {target}")
                    continue
                edges.setdefault(source, []).append(target)
                if source == "ppt/presentation.xml" and rel.get("Type") == SLIDE_REL:
                    slide_targets[rel_id] = target

        # Orphans: every part must be reachable from the package relationships.
        reachable: set[str] = set()
        queue: deque[str] = deque([""])
        while queue:
            part = queue.popleft()
            for target in edges.get(part, []):
                if target not in reachable:
                    reachable.add(target)
                    queue.append(target)
        for name in names:
            if name == CONTENT_TYPES or name.endswith(".rels"):
                if name.endswith(".rels") and name != "_rels/.rels":
                    source = _source_of(name)
                    if source in name_set and source not in reachable:
                        problems.append(f"orphan relationships: {name}")
                continue
            if name not in reachable:
                problems.append(f"orphan part: {name}")

        # Slide list.
        presentation = trees.get("ppt/presentation.xml")
        if presentation is None:
            problems.append("missing ppt/presentation.xml")
        else:
            seen_ids: set[str] = set()
            seen_rels: set[str] = set()
            for entry in presentation.iter(f"{{{P_NS}}}sldId"):
                slide_id = entry.get("id", "")
                rel_id = entry.get(f"{{{R_NS}}}id", "")
                if slide_id in seen_ids:
                    problems.append(f"duplicated slide id {slide_id}")
                if not slide_id.isdigit() or not 256 <= int(slide_id) < 2147483648:
                    problems.append(f"slide id out of range: {slide_id}")
                if rel_id in seen_rels:
                    problems.append(f"slide relationship used twice: {rel_id}")
                if rel_id not in slide_targets:
                    problems.append(f"sldId {slide_id} does not point to a slide ({rel_id})")
                seen_ids.add(slide_id)
                seen_rels.add(rel_id)
            unlisted = set(slide_targets) - seen_rels
            for rel_id in sorted(unlisted):
                problems.append(f"slide relationship not in sldIdLst: {rel_id}")

        if not allow_tags:
            content = [n for n in names if n.startswith(("ppt/slides/", "ppt/notesSlides/"))]
            for name in content:
                if name.endswith(".xml") and _LEFTOVER.search(archive.read(name)):
                    problems.append(f"leftover {{{{tag}}}} or @pallotti in {name}")

    try:
        from pptx import Presentation

        Presentation(str(path))
    except Exception as error:  # any failure to open is a problem
        problems.append(f"python-pptx cannot open the file: {error}")
    return problems


def main(argv: list[str]) -> int:
    allow_tags = "--allow-tags" in argv
    files = [Path(arg) for arg in argv if arg != "--allow-tags"]
    if not files:
        print(__doc__)
        return 2
    failed = False
    for file in files:
        problems = validate(file, allow_tags=allow_tags)
        if problems:
            failed = True
            print(f"INVÁLIDO: {file} ({len(problems)} problema(s))")
            for problem in problems[:MAX_PRINTED]:
                print(f"  - {problem}")
            if len(problems) > MAX_PRINTED:
                print(f"  ... e mais {len(problems) - MAX_PRINTED}")
        else:
            print(f"OK: {file}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
