"""Duplicate, remove and reorder slides and replace tagged text at the XML level.

python-pptx cannot duplicate slides and ``text_frame.text = ...`` loses the formatting, so the
generator works on the XML with lxml (namespaces preserved).
"""

import hashlib
import re
from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass

from lxml.etree import _Element
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part, PartFactory, XmlPart
from pptx.opc.packuri import PackURI
from pptx.presentation import Presentation
from pptx.slide import Slide, SlideLayout

_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_SKIPPED_RELATIONS = {RT.SLIDE_LAYOUT, RT.NOTES_SLIDE}
_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_CSLD = f"{{{_P_NS}}}cSld"
_SP_TREE = f"{{{_P_NS}}}spTree"


def _copy_common_slide_data(source: _Element, target: _Element) -> None:
    """Copy ``p:cSld`` (background + shape tree), keeping the target's ``p:spTree`` element."""
    target_tree = target.find(_SP_TREE)
    for child in list(target):
        if child is not target_tree:
            target.remove(child)
    for child in list(target_tree):
        target_tree.remove(child)
    after = target_tree
    seen_tree = False
    for child in source:
        if child.tag == _SP_TREE:
            seen_tree = True
            for name, value in child.attrib.items():
                target_tree.set(name, value)
            for grandchild in child:
                target_tree.append(deepcopy(grandchild))
        elif not seen_tree:
            target_tree.addprevious(deepcopy(child))
        else:
            after.addnext(deepcopy(child))
            after = after.getnext()


def _copy_slide_xml(source_root: _Element, target_root: _Element, renamed: dict[str, str]) -> None:
    """Make ``target_root`` (``p:sld``) a copy of ``source_root`` with relationship ids renamed.

    Edits in place (not replacing the root): python-pptx caches ``slide.shapes`` on the tree.
    """
    for name, value in source_root.attrib.items():
        target_root.set(name, value)
    for child in list(target_root):
        if child.tag != _CSLD:
            target_root.remove(child)
    for child in source_root:
        if child.tag != _CSLD:
            target_root.append(deepcopy(child))
    _copy_common_slide_data(source_root.find(_CSLD), target_root.find(_CSLD))
    _rename_relationship_ids(target_root, renamed)


def _rename_relationship_ids(root: _Element, renamed: dict[str, str]) -> None:
    prefix = f"{{{_R_NS}}}"
    for element in root.iter():
        for name, value in list(element.attrib.items()):
            if name.startswith(prefix) and value in renamed:
                element.set(name, renamed[value])


def duplicate_slide(presentation: Presentation, slide: Slide) -> Slide:
    """Append a copy of ``slide`` (same layout, same images) at the end of the deck.

    The copy gets its own slide part; images and other targets are shared with the original
    through new relationships. Notes are not copied.
    """
    copy: Slide = presentation.slides.add_slide(slide.slide_layout)
    new_part = copy.part

    renamed: dict[str, str] = {}
    for rel_id, rel in slide.part.rels.items():
        if rel.reltype in _SKIPPED_RELATIONS:
            continue
        if rel.is_external:
            renamed[rel_id] = new_part.relate_to(rel.target_ref, rel.reltype, is_external=True)
        else:
            renamed[rel_id] = new_part.relate_to(rel.target_part, rel.reltype)
    _copy_slide_xml(slide.element, copy.element, renamed)
    return copy


# --- Slides from another file (M3b) -------------------------------------------------------------

# Parts that belong to the deck structure: a slide never brings its own copy of them.
_STRUCTURAL_RELATIONS = {
    RT.SLIDE,
    RT.SLIDE_LAYOUT,
    RT.SLIDE_MASTER,
    RT.NOTES_SLIDE,
    RT.NOTES_MASTER,
}
_NUMBERED_NAME = re.compile(r"^(?P<stem>.*?)(?P<number>\d*)(?P<ext>\.[^./]+)$")


class SlideImportError(ValueError):
    """A slide of another file cannot be imported (missing layout, link to another slide)."""


class SlideImporter:
    """Appends slides of OTHER .pptx files to ``presentation`` (the generated deck).

    For each imported slide: the slide part is copied; its layout is the equivalent layout of
    ``presentation`` (same name and file, else same name; never a new layout); images and other
    targets are copied once and deduplicated by content (an image already in the deck is
    reused); the speaker notes are copied. Nothing new is drawn (CLAUDE.md, rule 2).
    One importer per destination deck: it remembers what was already copied.
    """

    def __init__(self, presentation: Presentation) -> None:
        self._presentation = presentation
        self._package = presentation.part.package
        self._copied: dict[int, tuple[Part, Part]] = {}  # id(source part) -> (source, copy)
        self._binary: dict[tuple[str, str], Part] | None = None  # (content type, sha1) -> part

    def import_slide(self, source: Slide) -> Slide:
        """Append a copy of ``source`` (a slide of another presentation) at the end."""
        layout = self._equivalent_layout(source.slide_layout)
        copy: Slide = self._presentation.slides.add_slide(layout)
        new_part = copy.part
        renamed: dict[str, str] = {}
        for rel_id, rel in source.part.rels.items():
            if rel.reltype in (RT.SLIDE_LAYOUT, RT.NOTES_SLIDE):
                continue
            if rel.is_external:
                renamed[rel_id] = new_part.relate_to(rel.target_ref, rel.reltype, is_external=True)
            elif rel.reltype in _STRUCTURAL_RELATIONS:
                raise SlideImportError(
                    f"O slide de {source.part.partname} aponta para outro slide ({rel.reltype})."
                )
            else:
                renamed[rel_id] = new_part.relate_to(self._copy_part(rel.target_part), rel.reltype)
        _copy_slide_xml(source.element, copy.element, renamed)
        if source.has_notes_slide:
            self._copy_notes(source, copy)
        return copy

    def _equivalent_layout(self, layout: SlideLayout) -> SlideLayout:
        candidates: list[SlideLayout] = [
            candidate
            for master in self._presentation.slide_masters
            for candidate in master.slide_layouts
            if candidate.name == layout.name
        ]
        for candidate in candidates:
            if candidate.part.partname == layout.part.partname:
                return candidate
        if candidates:
            return candidates[0]
        raise SlideImportError(f"O modelo não tem o layout {layout.name!r}.")

    @staticmethod
    def _copy_notes(source: Slide, target: Slide) -> None:
        source_csld = source.notes_slide.element.find(_CSLD)
        target_csld = target.notes_slide.element.find(_CSLD)
        if source_csld is None or target_csld is None:
            return
        has_relations = any(
            name.startswith(f"{{{_R_NS}}}")
            for element in source_csld.iter()
            for name in element.attrib
        )
        if not has_relations:  # notes with pictures are not supported: keep the empty notes
            _copy_common_slide_data(source_csld, target_csld)

    def _binary_parts(self) -> dict[tuple[str, str], Part]:
        if self._binary is None:
            self._binary = {
                (part.content_type, hashlib.sha1(part.blob).hexdigest()): part
                for part in self._package.iter_parts()
                if not isinstance(part, XmlPart)
            }
        return self._binary

    def _copy_part(self, source: Part) -> Part:
        """The destination part equivalent to ``source`` (copied once, binaries deduplicated)."""
        known = self._copied.get(id(source))
        if known is not None:
            return known[1]
        blob = source.blob
        key = (source.content_type, hashlib.sha1(blob).hexdigest())
        binary = not isinstance(source, XmlPart)
        if binary and key in self._binary_parts():
            part = self._binary_parts()[key]
            self._copied[id(source)] = (source, part)
            return part
        part = PartFactory(
            self._free_partname(source.partname), source.content_type, self._package, blob
        )
        self._copied[id(source)] = (source, part)
        if binary:
            self._binary_parts()[key] = part
        renamed: dict[str, str] = {}
        for rel_id, rel in source.rels.items():
            if rel.is_external:
                renamed[rel_id] = part.relate_to(rel.target_ref, rel.reltype, is_external=True)
            elif rel.reltype in _STRUCTURAL_RELATIONS:
                raise SlideImportError(f"{source.partname} aponta para {rel.reltype}.")
            else:
                renamed[rel_id] = part.relate_to(self._copy_part(rel.target_part), rel.reltype)
        if isinstance(part, XmlPart) and renamed:
            _rename_relationship_ids(part._element, renamed)
        return part

    def _free_partname(self, name: str) -> PackURI:
        """``/ppt/media/image7.jpeg`` -> first free ``/ppt/media/imageN.jpeg`` of the deck."""
        match = _NUMBERED_NAME.match(name)
        stem, ext = (match["stem"], match["ext"]) if match else (name, "")
        used = {str(part.partname) for part in self._package.iter_parts()}
        used.update(str(copy.partname) for _, copy in self._copied.values())
        number = 1
        while f"{stem}{number}{ext}" in used:
            number += 1
        return PackURI(f"{stem}{number}{ext}")


def keep_slides(presentation: Presentation, ordered: Sequence[Slide]) -> None:
    """Keep only ``ordered``, in that order; every other slide is removed from the deck.

    Removed slide parts become unreachable and are not written on save. Slide parts are
    renamed ``slide1.xml``… following the final order.
    """
    id_list = presentation.slides._sldIdLst
    by_id = {entry.id: entry for entry in id_list}
    wanted = [slide.slide_id for slide in ordered]
    for entry in list(id_list):
        if entry.id not in wanted:
            presentation.part.drop_rel(entry.rId)
        id_list.remove(entry)
    for slide_id in wanted:
        id_list.append(by_id[slide_id])
    presentation.part.rename_slide_parts([entry.rId for entry in id_list])


# --- Text at the run level (M3) -----------------------------------------------------------------

_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_A_P = f"{{{_A_NS}}}p"
_A_R = f"{{{_A_NS}}}r"
_A_T = f"{{{_A_NS}}}t"
_A_PPR = f"{{{_A_NS}}}pPr"
_A_RPR = f"{{{_A_NS}}}rPr"
_A_END = f"{{{_A_NS}}}endParaRPr"
_TAG = re.compile(r"\{\{(.*?)\}\}")


@dataclass(frozen=True)
class BodyLine:
    """One line (paragraph) of a song body."""

    text: str
    bold: bool


def text_tags(element: _Element) -> list[str]:
    """Names of every ``{{tag}}`` still written in the runs under ``element``."""
    return [name.strip() for t in element.iter(_A_T) for name in _TAG.findall(t.text or "")]


def replace_run_tags(element: _Element, values: Callable[[str], str]) -> None:
    """Replace each ``{{tag}}`` inside its run by ``values(tag)``; run formatting is kept."""
    for t in element.iter(_A_T):
        text = t.text or ""
        if "{{" in text:
            t.text = _TAG.sub(lambda match: values(match.group(1).strip()), text)


def find_tag_paragraph(element: _Element, tag: str) -> _Element | None:
    """The ``a:p`` whose runs hold ``{{tag}}``."""
    marker = f"{{{{{tag}}}}}"
    for run in element.iter(_A_R):
        t = run.find(_A_T)
        if t is not None and marker in (t.text or ""):
            return run.getparent()
    return None


def _set_size_and_bold(run_props: _Element, size_pt: int, bold: bool) -> None:
    run_props.set("sz", str(size_pt * 100))
    run_props.set("b", "1" if bold else "0")


def replace_body(element: _Element, tag: str, lines: Sequence[BodyLine], size_pt: int) -> None:
    """Replace the paragraph holding ``{{tag}}`` by one centred paragraph per line.

    Each new paragraph copies the ``a:pPr`` of the prototype paragraph (with ``algn="ctr"``)
    and its run copies the ``a:rPr`` of the tag run, with ``sz`` = ``size_pt`` and ``b`` from
    the line. Nothing else of the shape changes.
    """
    paragraph = find_tag_paragraph(element, tag)
    if paragraph is None:
        raise ValueError(f"{{{{{tag}}}}} not found")
    marker = f"{{{{{tag}}}}}"
    proto_run = next(run for run in paragraph.iter(_A_R) if marker in (run.findtext(_A_T) or ""))
    proto_ppr = paragraph.find(_A_PPR)
    proto_end = paragraph.find(_A_END)
    anchor = paragraph
    for line in lines or [BodyLine("", False)]:
        new = deepcopy(paragraph)
        for child in list(new):
            new.remove(child)
        ppr = deepcopy(proto_ppr) if proto_ppr is not None else new.makeelement(_A_PPR, {})
        ppr.set("algn", "ctr")
        new.append(ppr)
        if line.text:
            run = deepcopy(proto_run)
            run_props = run.find(_A_RPR)
            if run_props is None:
                run_props = run.makeelement(_A_RPR, {})
                run.insert(0, run_props)
            _set_size_and_bold(run_props, size_pt, line.bold)
            t = run.find(_A_T)
            assert t is not None
            t.text = line.text
            new.append(run)
        if proto_end is not None:
            end = deepcopy(proto_end)
            _set_size_and_bold(end, size_pt, line.bold)
            new.append(end)
        anchor.addnext(new)
        anchor = new
    parent = paragraph.getparent()
    assert parent is not None
    parent.remove(paragraph)


def remove_note_lines(notes: _Element, prefix: str) -> None:
    """Remove from a notes slide every paragraph whose text starts with ``prefix``.

    A text body left without paragraphs gets one empty paragraph (required by the schema).
    """
    for paragraph in list(notes.iter(_A_P)):
        text = "".join(t.text or "" for t in paragraph.iter(_A_T))
        if text.strip().startswith(prefix):
            body = paragraph.getparent()
            assert body is not None
            body.remove(paragraph)
            if body.find(_A_P) is None:
                body.append(body.makeelement(_A_P, {}))
