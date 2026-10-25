"""PptxBuilder + slides_xml: slides copied/removed/reordered, tags filled, notes cleaned."""

import importlib.util
import io
import zipfile
from pathlib import Path
from types import ModuleType

import pytest
from lxml import etree
from pptx import Presentation

from pallotti_slides.domain.models import Line
from pallotti_slides.presentation.builder import PptxBuilder
from pallotti_slides.presentation.errors import TemplateError
from pallotti_slides.presentation.planner import SlidePlan, TargetSlide, TextContent
from pallotti_slides.presentation.slides_xml import (
    BodyLine,
    remove_note_lines,
    replace_body,
    replace_run_tags,
    text_tags,
)
from pallotti_slides.presentation.template import MassTemplate, default_template_path

ROOT = Path(__file__).resolve().parents[3]
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_ooxml", ROOT / "scripts" / "validate_ooxml.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator()


def body(lines: list[Line], size: int = 48) -> TextContent:
    return TextContent(lines=tuple(lines), size_pt=size)


@pytest.fixture
def small_plan(template: MassTemplate) -> SlidePlan:
    """Title slide, the mantra prototype twice and the second-reading slide, reordered."""
    mantra = template.slides[2]
    reading = template.slides[13]
    assert mantra.tag.moment is not None and "liturgy.second_reading" in reading.fields
    return SlidePlan(
        [
            TargetSlide(1, {"celebration.title": TextContent(text="Título & <teste>")}),
            TargetSlide(
                2,
                {
                    "song.label": TextContent(text="Mantra"),
                    "song.text": body([Line(text="Refrão", bold=True), Line(text="Verso")], 52),
                },
            ),
            TargetSlide(
                2,
                {
                    "song.label": TextContent(text="Mantra"),
                    "song.text": body([Line(text="Segunda página")], 52),
                },
            ),
            TargetSlide(13, {"liturgy.second_reading": TextContent(text="Fl 2,1-11")}),
        ]
    )


def texts(slide: object) -> list[str]:
    return [
        p.text
        for shape in slide.shapes  # type: ignore[attr-defined]
        if shape.has_text_frame
        for p in shape.text_frame.paragraphs
        if p.text
    ]


def test_build_small_plan(tmp_path: Path, small_plan: SlidePlan) -> None:
    destination = tmp_path / "saida" / "missa.pptx"
    before = default_template_path().read_bytes()
    assert PptxBuilder().build(default_template_path(), small_plan, destination) == destination
    assert default_template_path().read_bytes() == before  # template untouched
    assert not list(destination.parent.glob(".*"))  # no temporary file left

    deck = Presentation(str(destination))
    slides = list(deck.slides)
    assert len(slides) == 4
    assert "Título & <teste>" in texts(slides[0])
    assert sorted(texts(slides[1])) == ["Mantra", "Refrão", "Verso"]
    assert "Segunda página" in texts(slides[2])
    assert "Fl 2,1-11" in texts(slides[3])
    assert VALIDATOR.validate(destination) == []


def test_song_body_is_centred_sized_and_bold_per_line(
    tmp_path: Path, small_plan: SlidePlan
) -> None:
    destination = PptxBuilder().build(default_template_path(), small_plan, tmp_path / "m.pptx")
    slide = list(Presentation(str(destination)).slides)[1]
    shape = next(s for s in slide.shapes if s.has_text_frame and "Refrão" in s.text_frame.text)
    paragraphs = shape.text_frame.paragraphs
    assert [p.text for p in paragraphs] == ["Refrão", "Verso"]
    for paragraph, bold in zip(paragraphs, (True, False), strict=True):
        ppr = paragraph._p.find(f"{A}pPr")
        assert ppr is not None and ppr.get("algn") == "ctr"
        assert ppr.find(f"{A}lnSpc") is not None  # copied from the prototype
        (run,) = paragraph.runs
        assert run.font.size.pt == 52
        assert run.font.bold is bold
        assert run.font.name == "Aptos"  # rPr of the prototype kept


def test_copies_share_images_and_notes_lose_the_tags(
    tmp_path: Path, template: MassTemplate
) -> None:
    separator = next(s for s in template.slides if s.tag.group == "canto:entrada")
    plan = SlidePlan([TargetSlide(separator.index), TargetSlide(separator.index)])
    destination = PptxBuilder().build(default_template_path(), plan, tmp_path / "m.pptx")
    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
        media = [n for n in names if n.startswith("ppt/media/")]
        notes = [n for n in names if n.startswith("ppt/notesSlides/notesSlide")]
        for name in notes:
            assert b"@pallotti" not in archive.read(name)
    assert len(media) == 1
    assert VALIDATOR.validate(destination) == []


def test_missing_value_for_a_tag_is_an_error(tmp_path: Path) -> None:
    plan = SlidePlan([TargetSlide(1, {})])
    with pytest.raises(TemplateError, match=r"celebracao\.titulo"):
        PptxBuilder().build(default_template_path(), plan, tmp_path / "m.pptx")
    assert not (tmp_path / "m.pptx").exists()


def test_source_outside_the_template_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(TemplateError, match="não existe"):
        PptxBuilder().build(
            default_template_path(), SlidePlan([TargetSlide(999)]), tmp_path / "m.pptx"
        )


# --- slides_xml helpers on small XML ------------------------------------------------------------

NS = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def xml(text: str) -> etree._Element:
    return etree.fromstring(f"<root {NS}>{text}</root>")


def test_replace_run_tags_keeps_the_run_properties() -> None:
    root = xml(
        '<a:p><a:r><a:rPr sz="4800" b="1"/><a:t>Salmo {{liturgia.salmo_numero}}</a:t></a:r></a:p>'
    )
    replace_run_tags(root, lambda tag: {"liturgia.salmo_numero": "24(25)"}[tag])
    run = root.find(f".//{A}r")
    assert run is not None
    assert run.findtext(f"{A}t") == "Salmo 24(25)"
    assert run.find(f"{A}rPr").get("sz") == "4800"  # type: ignore[union-attr]
    assert text_tags(root) == []


def test_replace_body_builds_one_paragraph_per_line() -> None:
    root = xml(
        '<a:txBody><a:p><a:pPr algn="l" marL="1"/><a:r><a:rPr sz="5400" b="1"/>'
        '<a:t>{{canto.texto}}</a:t></a:r><a:endParaRPr sz="5400"/></a:p></a:txBody>'
    )
    replace_body(root, "canto.texto", [BodyLine("Um", True), BodyLine("", False)], 44)
    paragraphs = root.findall(f".//{A}p")
    assert len(paragraphs) == 2
    assert [p.find(f"{A}pPr").get("algn") for p in paragraphs] == ["ctr", "ctr"]  # type: ignore[union-attr]
    assert paragraphs[0].find(f"{A}pPr").get("marL") == "1"  # type: ignore[union-attr]
    run_props = paragraphs[0].find(f"{A}r/{A}rPr")
    assert run_props is not None
    assert (run_props.get("sz"), run_props.get("b")) == ("4400", "1")
    assert paragraphs[1].find(f"{A}r") is None  # empty line = empty paragraph
    assert paragraphs[1].find(f"{A}endParaRPr").get("sz") == "4400"  # type: ignore[union-attr]
    assert text_tags(root) == []


def test_remove_note_lines_keeps_other_notes() -> None:
    root = xml(
        "<a:txBody><a:p><a:r><a:t>@pallotti fixo</a:t></a:r></a:p>"
        "<a:p><a:r><a:t>Lembrar de baixar a luz</a:t></a:r></a:p></a:txBody>"
    )
    remove_note_lines(root, "@pallotti")
    assert [t.text for t in root.iter(f"{A}t")] == ["Lembrar de baixar a luz"]
    only = xml("<a:txBody><a:p><a:r><a:t>@pallotti fixo</a:t></a:r></a:p></a:txBody>")
    remove_note_lines(only, "@pallotti")
    assert len(only.findall(f".//{A}p")) == 1  # schema needs one paragraph
    assert list(only.iter(f"{A}t")) == []


# --- validator ---------------------------------------------------------------------------------


def rewrite(source: Path, destination: Path, change: dict[str, bytes | None]) -> Path:
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(destination, "w") as new:
        for item in old.infolist():
            if item.filename in change:
                data = change[item.filename]
                if data is not None:
                    new.writestr(item, data)
            else:
                new.writestr(item, old.read(item.filename))
        for name, data in change.items():
            if name not in old.namelist() and data is not None:
                new.writestr(name, data)
    return destination


def test_validator_detects_broken_packages(tmp_path: Path, small_plan: SlidePlan) -> None:
    good = PptxBuilder().build(default_template_path(), small_plan, tmp_path / "ok.pptx")
    assert VALIDATOR.validate(good) == []

    orphan = rewrite(good, tmp_path / "orphan.pptx", {"ppt/media/extra.jpeg": b"x"})
    assert any("orphan part" in p for p in VALIDATOR.validate(orphan))

    missing = rewrite(good, tmp_path / "missing.pptx", {"ppt/slides/slide2.xml": None})
    problems = VALIDATOR.validate(missing)
    assert any("missing part" in p for p in problems)

    with zipfile.ZipFile(good) as archive:
        presentation = archive.read("ppt/presentation.xml")
    first_id = presentation.split(b'<p:sldId id="')[1].split(b'"')[0]
    second_id = presentation.split(b'<p:sldId id="')[2].split(b'"')[0]
    duplicated = presentation.replace(b'id="' + second_id + b'"', b'id="' + first_id + b'"', 1)
    dup = rewrite(good, tmp_path / "dup.pptx", {"ppt/presentation.xml": duplicated})
    assert any("duplicated slide id" in p for p in VALIDATOR.validate(dup))

    broken = rewrite(good, tmp_path / "broken.pptx", {"ppt/slides/slide1.xml": b"<p:sld"})
    assert any("malformed XML" in p for p in VALIDATOR.validate(broken))

    tagged = VALIDATOR.validate(default_template_path())
    assert any("leftover" in p for p in tagged)
    assert VALIDATOR.validate(default_template_path(), allow_tags=True) == []

    not_zip = tmp_path / "x.pptx"
    not_zip.write_bytes(b"nope")
    assert VALIDATOR.validate(not_zip) != []


def test_validator_cli_exit_codes(
    tmp_path: Path, small_plan: SlidePlan, capsys: pytest.CaptureFixture[str]
) -> None:
    good = PptxBuilder().build(default_template_path(), small_plan, tmp_path / "ok.pptx")
    assert VALIDATOR.main([str(good)]) == 0
    assert VALIDATOR.main([str(default_template_path())]) == 1
    assert "INVÁLIDO" in capsys.readouterr().out


def test_saved_deck_reloads_in_memory(tmp_path: Path, small_plan: SlidePlan) -> None:
    destination = PptxBuilder().build(default_template_path(), small_plan, tmp_path / "m.pptx")
    deck = Presentation(io.BytesIO(destination.read_bytes()))
    assert len(deck.slides) == 4
