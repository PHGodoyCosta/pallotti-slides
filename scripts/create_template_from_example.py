"""Builds src/pallotti_slides/resources/template/mass_template.pptx from the example deck.

Reads ``examples/Missa - 26° Dom do T.C - 26.09.2026 - OE III.pptx`` (read-only) and, following
docs/MODELO_PPTX.md:

* keeps ONE prototype slide per song moment and replaces its texts by ``{{canto.rotulo}}`` and
  ``{{canto.texto}}``;
* writes the ``@pallotti ...`` tag on the first line of each slide's notes;
* replaces the variable texts by ``{{...}}`` tags (inside the original run, so the formatting
  stays);
* adds the communion / post-communion / recessional songs, by copying existing slides;
* moves each Eucharistic prayer block to its own file,
  ``src/pallotti_slides/resources/eucharistic_prayers/<id>.pptx`` (slides untouched), and leaves
  in the template only the marker ``@pallotti oe=slot`` (a copy of the first slide of the block,
  never shown in a generated deck).

Nothing is drawn by code: slides are only kept, removed, copied and reordered.
Every slide number below is a slide of the EXAMPLE (1-based). The values marked PROVISIONAL are
decisions waiting for Pedro's approval; change them here and run the script again.

Usage: uv run python scripts/create_template_from_example.py
"""

import sys
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

from pptx import Presentation
from pptx.presentation import Presentation as PresentationType
from pptx.shapes.autoshape import Shape
from pptx.slide import Slide
from pptx.util import Emu

from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import Mass
from pallotti_slides.presentation.slides_xml import duplicate_slide, keep_slides
from pallotti_slides.presentation.template import (
    MOMENT_TAGS,
    PRAYER_SLOT_ID,
    SECOND_READING_GROUP,
    SONG_GROUP_PREFIX,
    TAG_PREFIX,
    MassTemplate,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "Missa - 26° Dom do T.C - 26.09.2026 - OE III.pptx"
FIXTURE = ROOT / "tests" / "fixtures" / "masses" / "26tc_2026.json"
OUTPUT = ROOT / "src" / "pallotti_slides" / "resources" / "template" / "mass_template.pptx"
PRAYERS_DIR = ROOT / "src" / "pallotti_slides" / "resources" / "eucharistic_prayers"

# --- Song moments of the example -------------------------------------------------------------
# The prototype is the first slide of each song block; the other slides of the block go away.
PROTOTYPES: dict[SongMoment, int] = {
    SongMoment.MANTRA: 3,
    SongMoment.ENTRANCE: 5,
    SongMoment.PENITENTIAL_ACT: 10,
    SongMoment.GLORIA: 15,
    SongMoment.ACCLAMATION: 26,
    SongMoment.OFFERTORY: 36,
}
# Separator image that precedes the song and disappears together with it.
SEPARATORS: dict[SongMoment, int] = {
    SongMoment.ENTRANCE: 4,
    SongMoment.PENITENTIAL_ACT: 9,
    SongMoment.GLORIA: 14,
    SongMoment.OFFERTORY: 35,
}
# Body boxes (M3-fix, approved by Pedro). The offertory prototype (and so the copies made from it:
# communion, post-communion, recessional) gets the position/width of the other prototypes; every
# song prototype body then goes down to BODY_BOTTOM_MARGIN_EMU above the slide bottom.
WIDE_BODY_LEFT = 114480
WIDE_BODY_WIDTH = 11944080
WIDE_BODY_MOMENTS = frozenset({SongMoment.OFFERTORY})
BODY_BOTTOM_MARGIN_EMU = 182880  # 0.2"
SONG_SLIDES_TO_DROP = {6, 7, 8, 11, 12, 13, 16, 17, 18, 19, 37, 38, 39}

# Slides that go away together when there is no second reading.
SECOND_READING_SLIDES = (24, 25)

# --- Eucharistic prayer block (PROVISIONAL) --------------------------------------------------
PRAYER_ID = "III"
PRAYER_SLIDES = range(47, 61)  # 47..60
# Block "Diversas Circunstâncias IV" (tag ``oe=DC_IV``, enum value "DC IV"), placed right after the
# OE III block. Built only by duplicating slides of the OE III block. Each entry is
# (source slide, new text of the black run or None to keep it); every response is preceded by a
# copy of the host image (slide 47). Texts supplied by Pedro (2026-10-24).
PRAYER_DC_IV_TAG = "DC_IV"
PRAYER_DC_IV_IMAGE = 47
PRAYER_DC_IV_AFTER = 60
PRAYER_DC_IV_SLIDES: tuple[tuple[int, str | None], ...] = (
    (48, "Bendito o vosso Filho, presente entre nós!"),
    (48, None),  # Enviai o vosso Espírito Santo!
    (50, None),  # {{liturgia.misterio_fe}}
    (52, "Aceitai, ó Senhor, a nossa oferta!"),
    (54, "O Espírito nos una num só corpo!"),
    (54, "Confirmai na unidade a vossa Igreja!"),
    (54, "Ajudai-nos a criar um mundo novo!"),
    (54, "Concedei-lhes, ó Senhor, a luz eterna!"),
    (60, None),  # Amém!
)

# --- End of the Mass (PROVISIONAL) -----------------------------------------------------------
# Before the final slide 69 come, in this order, a separator + prototype for each moment below.
FINAL_SLIDE = 69
NEW_SONGS = (SongMoment.COMMUNION, SongMoment.POST_COMMUNION, SongMoment.RECESSIONAL)
NEW_SEPARATOR_SOURCE = 4  # Jesus image: always the separator image
NEW_PROTOTYPE_SOURCE = 36  # offertory prototype

# --- Text tags: (example slide, field of the reference Mass, tag in the template) ------------
# The old text must exist, exactly, in ONE run of the slide (sanity check against the fixture).
TEXT_TAGS: tuple[tuple[int, str, str], ...] = (
    (2, "celebration.title", "celebracao.titulo"),
    (21, "liturgy.first_reading", "liturgia.primeira_leitura"),
    (23, "liturgy.psalm_number", "liturgia.salmo_numero"),
    (23, "liturgy.psalm_refrain", "liturgia.salmo_refrao"),
    (24, "liturgy.second_reading", "liturgia.segunda_leitura"),
    (28, "liturgy.gospel", "liturgia.evangelho"),
    (31, "liturgy.intercessions_response", "liturgia.preces_refrao"),
    (50, "liturgy.mystery_of_faith", "liturgia.misterio_fe"),
)


def fail(message: str) -> None:
    sys.exit(f"ERRO: {message}")


def text_shapes(slide: Slide) -> list[Shape]:
    return [s for s in slide.shapes if isinstance(s, Shape) and s.has_text_frame]


def replace_run_text(slide: Slide, number: int, old: str, new: str) -> None:
    """Replace the text of the single run that holds exactly ``old`` (formatting is kept)."""
    runs = [
        run
        for shape in text_shapes(slide)
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
        if run.text == old
    ]
    if len(runs) != 1:
        fail(f"slide {number}: esperava 1 trecho com {old!r}, achei {len(runs)}")
    runs[0].text = new


def make_song_prototype(
    slide: Slide, number: int, moment: SongMoment, presentation_height: int
) -> None:
    """Label -> ``{{canto.rotulo}}``; body -> one paragraph with ``{{canto.texto}}``.

    The body box is also resized (see ``WIDE_BODY_*`` and ``BODY_BOTTOM_MARGIN_EMU``).
    """
    shapes = text_shapes(slide)
    labels = [s for s in shapes if s.text_frame.text.strip() == moment.label]
    if len(labels) != 1:
        fail(f"slide {number}: rótulo {moment.label!r} não encontrado (achei {len(labels)})")
    label = labels[0]
    bodies = [s for s in shapes if s is not label and s.text_frame.text.strip()]
    if len(bodies) != 1:
        fail(f"slide {number}: esperava 1 corpo de canto, achei {len(bodies)}")
    body = bodies[0]

    label.text_frame.paragraphs[0].runs[0].text = "{{canto.rotulo}}"

    paragraphs = body.text_frame.paragraphs
    first = paragraphs[0]
    for paragraph in paragraphs[1:]:
        paragraph._p.getparent().remove(paragraph._p)
    for run in first.runs[1:]:
        run._r.getparent().remove(run._r)
    first.runs[0].text = "{{canto.texto}}"

    # Only the xfrm of the existing box changes.
    slide_height = int(presentation_height)
    if moment in WIDE_BODY_MOMENTS:
        body.left = Emu(WIDE_BODY_LEFT)
        body.width = Emu(WIDE_BODY_WIDTH)
    body.height = Emu(slide_height - BODY_BOTTOM_MARGIN_EMU - int(body.top or 0))


def dc_iv_block(
    presentation: PresentationType, slide_of: Callable[[int], Slide]
) -> list[tuple[Slide, str]]:
    """Slides of the DC IV block: image + response, copied from the OE III block."""
    tag = f"oe={PRAYER_DC_IV_TAG}"
    block: list[tuple[Slide, str]] = []
    for source, text in PRAYER_DC_IV_SLIDES:
        block.append((duplicate_slide(presentation, slide_of(PRAYER_DC_IV_IMAGE)), tag))
        response = duplicate_slide(presentation, slide_of(source))
        if text is not None:
            runs = [
                r
                for shape in text_shapes(response)
                for p in shape.text_frame.paragraphs
                for r in p.runs
            ]
            if len(runs) < 3 or runs[0].text != "R:":
                fail(f"slide {source}: esperava run vermelho 'R:' seguido do texto da resposta")
            runs[2].text = text  # the black run; the red "R:" run stays untouched
        block.append((response, tag))
    return block


def set_tag(slide: Slide, tag: str) -> None:
    slide.notes_slide.notes_text_frame.text = f"{TAG_PREFIX} {tag}"


def get_tag(slide: Slide) -> str:
    text = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
    return text.strip().removeprefix(TAG_PREFIX).strip()


def split_prayer_blocks(full: bytes) -> list[str]:
    """Write the template (marker in place of the blocks) and one file per prayer block.

    ``full`` is the template with every block inside (tags ``oe=<id>``). Each file is that
    same deck reduced to some of its slides, so the slides are not touched.
    """
    deck = Presentation(BytesIO(full))
    slides = list(deck.slides)
    tags = [get_tag(slide) for slide in slides]
    ids = list(dict.fromkeys(t.removeprefix("oe=") for t in tags if t.startswith("oe=")))
    if not ids:
        fail("o modelo completo não tem blocos de OE")
    first = next(i for i, tag in enumerate(tags) if tag.startswith("oe="))
    marker = duplicate_slide(deck, slides[first])
    set_tag(marker, f"oe={PRAYER_SLOT_ID}")
    kept = [*slides[:first], marker]
    kept += [
        s for s, tag in zip(slides[first:], tags[first:], strict=True) if not tag.startswith("oe=")
    ]
    keep_slides(deck, kept)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    deck.save(str(OUTPUT))
    print(f"Modelo gravado em {OUTPUT} ({len(kept)} slides)")

    PRAYERS_DIR.mkdir(parents=True, exist_ok=True)
    for prayer in ids:
        deck = Presentation(BytesIO(full))
        block = [s for s in deck.slides if get_tag(s) == f"oe={prayer}"]
        keep_slides(deck, block)
        path = PRAYERS_DIR / f"{prayer}.pptx"
        deck.save(str(path))
        print(f"Bloco da OE gravado em {path} ({len(block)} slides)")
    return ids


def main() -> None:
    if not EXAMPLE.is_file():
        fail(f"exemplo não encontrado: {EXAMPLE}")
    mass = Mass.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    values: dict[str, str] = {"celebration.title": mass.celebration.title}
    for name, value in mass.liturgy.model_dump().items():
        if isinstance(value, str):
            values[f"liturgy.{name}"] = value

    presentation = Presentation(str(EXAMPLE))
    original = list(presentation.slides)
    if len(original) != FINAL_SLIDE:
        fail(f"o exemplo deveria ter {FINAL_SLIDE} slides, tem {len(original)}")

    def slide_of(number: int) -> Slide:
        return original[number - 1]

    # 1. Texts: song prototypes and variable fields (before copying, so copies inherit them).
    for moment, number in PROTOTYPES.items():
        make_song_prototype(slide_of(number), number, moment, int(presentation.slide_height or 0))
    for number, field, tag in TEXT_TAGS:
        replace_run_text(slide_of(number), number, values[field], f"{{{{{tag}}}}}")

    # 2. Tags for the slides that stay from the example.
    tags: dict[int, str] = {number: "fixo" for number in range(1, FINAL_SLIDE + 1)}
    for moment, number in PROTOTYPES.items():
        tags[number] = f"canto={MOMENT_TAGS[moment]}"
    for moment, number in SEPARATORS.items():
        tags[number] = f"grupo={SONG_GROUP_PREFIX}{MOMENT_TAGS[moment]}"
    for number in SECOND_READING_SLIDES:
        tags[number] = f"grupo={SECOND_READING_GROUP}"
    for number in PRAYER_SLIDES:
        tags[number] = f"oe={PRAYER_ID}"

    # 3. Final order: example slides (minus the dropped ones) + the new songs before slide 69.
    ordered: list[tuple[Slide, str]] = []
    for number in range(1, FINAL_SLIDE + 1):
        if number in SONG_SLIDES_TO_DROP:
            continue
        if number == FINAL_SLIDE:
            for moment in NEW_SONGS:
                group = f"{SONG_GROUP_PREFIX}{MOMENT_TAGS[moment]}"
                separator = duplicate_slide(presentation, slide_of(NEW_SEPARATOR_SOURCE))
                prototype = duplicate_slide(presentation, slide_of(NEW_PROTOTYPE_SOURCE))
                ordered.append((separator, f"grupo={group}"))
                ordered.append((prototype, f"canto={MOMENT_TAGS[moment]}"))
        ordered.append((slide_of(number), tags[number]))
        if number == PRAYER_DC_IV_AFTER:
            ordered.extend(dc_iv_block(presentation, slide_of))

    # 4. Keep/reorder/rename, then write the tags in the notes.
    keep_slides(presentation, [slide for slide, _ in ordered])
    for slide, tag in ordered:
        set_tag(slide, tag)

    # 5. Prayer blocks to their own files; the template keeps only the marker.
    full = BytesIO()
    presentation.save(full)
    split_prayer_blocks(full.getvalue())

    # 6. Check the result with the same code the program uses.
    problems = MassTemplate.load(OUTPUT, PRAYERS_DIR).validate()
    for notice in problems:
        print(f"{notice.level.upper()}: {notice.field or '-'}: {notice.message}")
    if any(notice.level == "error" for notice in problems):
        sys.exit(1)


if __name__ == "__main__":
    main()
