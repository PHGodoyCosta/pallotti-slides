"""Duplicate, remove and reorder slides at the XML level (python-pptx cannot do it).

M2 needs ``duplicate_slide`` and ``keep_slides``; M3 builds the generator on top of them.
"""

from collections.abc import Sequence
from copy import deepcopy

from lxml.etree import _Element
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.presentation import Presentation
from pptx.slide import Slide

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

    # Edit in place (not replace the root): python-pptx caches ``copy.shapes`` on the old tree.
    source_root = slide.element
    target_root = copy.element
    for name, value in source_root.attrib.items():
        target_root.set(name, value)
    for child in list(target_root):
        if child.tag != _CSLD:
            target_root.remove(child)
    for child in source_root:
        if child.tag != _CSLD:
            target_root.append(deepcopy(child))
    _copy_common_slide_data(source_root.find(_CSLD), target_root.find(_CSLD))

    prefix = f"{{{_R_NS}}}"
    for element in target_root.iter():
        for name, value in list(element.attrib.items()):
            if name.startswith(prefix) and value in renamed:
                element.set(name, renamed[value])
    return copy


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
