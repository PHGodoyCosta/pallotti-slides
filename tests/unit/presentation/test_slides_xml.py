"""Duplicate / keep / reorder slides at the XML level."""

import io
import zipfile

from pptx import Presentation

from pallotti_slides.presentation.slides_xml import duplicate_slide, keep_slides
from pallotti_slides.presentation.template import default_template_path


def reload(presentation: Presentation) -> Presentation:  # type: ignore[valid-type]
    buffer = io.BytesIO()
    presentation.save(buffer)
    buffer.seek(0)
    return Presentation(buffer)


def test_duplicate_slide_copies_content_and_shares_the_image() -> None:
    presentation = Presentation(str(default_template_path()))
    source = presentation.slides[3]  # separator image
    copy = duplicate_slide(presentation, source)

    assert len(presentation.slides) == 81
    assert presentation.slides[-1].slide_id == copy.slide_id
    assert copy.slide_layout.name == source.slide_layout.name
    source_pics = [s for s in source.shapes if s.shape_type == 13]
    copy_pics = [s for s in copy.shapes if s.shape_type == 13]
    assert len(copy_pics) == len(source_pics) == 1
    assert copy_pics[0].image.sha1 == source_pics[0].image.sha1  # type: ignore[attr-defined]


def test_duplicate_slide_survives_save_and_reload() -> None:
    presentation = Presentation(str(default_template_path()))
    prototype = next(
        s
        for s in presentation.slides
        if any(sh.has_text_frame and "{{canto.texto}}" in sh.text_frame.text for sh in s.shapes)
    )
    duplicate_slide(presentation, prototype)
    reloaded = reload(presentation)
    texts = [
        sh.text_frame.text
        for sh in reloaded.slides[-1].shapes
        if sh.has_text_frame and sh.text_frame.text
    ]
    assert "{{canto.texto}}" in texts
    assert "{{canto.rotulo}}" in texts


def test_keep_slides_removes_and_reorders() -> None:
    presentation = Presentation(str(default_template_path()))
    slides = list(presentation.slides)
    kept = [slides[5], slides[1], slides[0]]
    keep_slides(presentation, kept)

    reloaded = reload(presentation)
    assert len(reloaded.slides) == 3
    assert [s.slide_id for s in presentation.slides] == [s.slide_id for s in kept]


def test_keep_slides_drops_orphan_parts() -> None:
    presentation = Presentation(str(default_template_path()))
    keep_slides(presentation, [presentation.slides[0]])
    buffer = io.BytesIO()
    presentation.save(buffer)
    with zipfile.ZipFile(buffer) as archive:
        names = archive.namelist()
    assert [n for n in names if n.startswith("ppt/slides/slide")] == ["ppt/slides/slide1.xml"]
    assert len([n for n in names if n.startswith("ppt/notesSlides/")]) <= 2  # notes + rels
