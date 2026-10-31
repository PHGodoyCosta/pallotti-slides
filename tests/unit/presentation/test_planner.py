"""BuildPlanner: which slides go into the deck, from which file and with which texts (F8)."""

import shutil
from pathlib import Path

import pytest

from pallotti_slides.domain.enums import EucharisticPrayer, SongMoment
from pallotti_slides.domain.models import Mass
from pallotti_slides.presentation.errors import TemplateError
from pallotti_slides.presentation.planner import BuildPlanner, SlidePlan, TextContent
from pallotti_slides.presentation.song_cache import SongDeck
from pallotti_slides.presentation.template import (
    SECOND_READING_GROUP,
    MassTemplate,
    TagKind,
    TemplateSlide,
    default_prayers_dir,
)


def one_deck_per_song(mass: Mass) -> dict[SongMoment, SongDeck]:
    """Fake cached decks: one page per stanza (the planner never opens them)."""
    return {
        moment: SongDeck(path=Path(f"/cache/{moment.value}.pptx"), pages=len(song.sequence()))
        for moment, song in mass.songs.items()
    }


def template_slides(template: MassTemplate, plan: SlidePlan) -> list[TemplateSlide]:
    return [template.slides[t.source] for t in plan if t.deck is None]


def song_moments(plan: SlidePlan) -> list[str]:
    """Moments of the song slides, in order (from the fake deck names)."""
    found: list[str] = []
    for target in plan:
        deck = target.deck
        if deck is not None and deck.parent == Path("/cache") and deck.stem not in found:
            found.append(deck.stem)
    return found


def test_reference_mass_has_the_69_slides(template: MassTemplate, mass_26tc: Mass) -> None:
    plan = BuildPlanner().plan(template, mass_26tc, one_deck_per_song(mass_26tc))
    assert len(plan) == 69
    used = {t.source for t in plan if t.deck is None}
    removed = [s for s in template.slides if s.index not in used]
    absent = {SongMoment.COMMUNION, SongMoment.POST_COMMUNION, SongMoment.RECESSIONAL}
    # every prototype goes (songs come from the cache) and so does the prayer slot
    assert {s.tag.kind for s in removed} == {TagKind.SONG, TagKind.GROUP, TagKind.PRAYER_SLOT}
    assert {s.tag.moment for s in removed if s.tag.kind is TagKind.GROUP} == absent


def test_song_slides_come_from_the_cached_deck_with_the_label(
    template: MassTemplate, mass_26tc: Mass
) -> None:
    decks = one_deck_per_song(mass_26tc)
    plan = BuildPlanner().plan(template, mass_26tc, decks)
    entrance = [t for t in plan if t.deck == decks[SongMoment.ENTRANCE].path]
    assert [t.source for t in entrance] == [0, 1, 2, 3]  # order [1, 2, 3, 2] -> 4 pages
    for target in entrance:
        assert target.replacements == {"song.label": TextContent(text="Canto de Entrada")}
    prototype = template.prototype(SongMoment.ENTRANCE)
    assert prototype is not None
    separator = template.slides[prototype.index - 1]
    position = plan.slides.index(entrance[0])
    assert plan.slides[position - 1].source == separator.index


def test_same_deck_in_another_moment_only_changes_the_label(
    template: MassTemplate, mass_26tc: Mass
) -> None:
    deck = SongDeck(path=Path("/cache/shared.pptx"), pages=2)
    plan = BuildPlanner().plan(
        template, mass_26tc, {SongMoment.ENTRANCE: deck, SongMoment.RECESSIONAL: deck}
    )
    labels = [t.replacements["song.label"].text for t in plan if t.deck == deck.path]
    assert labels == ["Canto de Entrada"] * 2 + ["Canto de Saída"] * 2


def test_chosen_prayer_block_replaces_the_slot(template: MassTemplate, mass_26tc: Mass) -> None:
    plan = BuildPlanner().plan(template, mass_26tc, one_deck_per_song(mass_26tc))
    block = template.prayer_block(EucharisticPrayer.III)
    prayer = [t for t in plan if t.deck == block.path]
    assert [t.source for t in prayer] == list(range(len(block.slides)))
    slot = template.prayer_slot()
    assert slot is not None
    first = plan.slides.index(prayer[0])
    assert plan.slides[first - 1].source == slot.index - 1  # right where the slot was
    assert plan.slides[first - 1].deck is None
    other = template.prayer_block(EucharisticPrayer.VARIOUS_NEEDS_IV).path
    assert all(t.deck != other for t in plan)


def test_every_field_of_every_slide_gets_a_value(template: MassTemplate, mass_26tc: Mass) -> None:
    plan = BuildPlanner().plan(template, mass_26tc, one_deck_per_song(mass_26tc))
    block = template.prayer_block(EucharisticPrayer.III)
    for target in plan:
        if target.deck is None:
            assert set(target.replacements) == template.slides[target.source].fields
        elif target.deck == block.path:
            assert set(target.replacements) == block.slides[target.source].fields
    values = {
        name: content.text
        for target in plan
        for name, content in target.replacements.items()
        if not content.is_body
    }
    assert values["celebration.title"] == "26° Domingo do Tempo Comum"
    assert values["liturgy.first_reading"] == mass_26tc.liturgy.first_reading
    assert values["liturgy.mystery_of_faith"] == mass_26tc.liturgy.mystery_of_faith


def test_full_mass_without_gloria_nor_second_reading(
    template: MassTemplate, mass_full: Mass
) -> None:
    plan = BuildPlanner().plan(template, mass_full, one_deck_per_song(mass_full))
    slides = template_slides(template, plan)
    assert all(s.tag.moment is not SongMoment.GLORIA for s in slides)
    assert all(s.tag.group != SECOND_READING_GROUP for s in slides)
    expected = [m.value for m in SongMoment if m is not SongMoment.GLORIA]
    assert song_moments(plan) == expected


def test_has_gloria_false_removes_gloria_even_with_a_song(
    template: MassTemplate, mass_26tc: Mass
) -> None:
    mass = mass_26tc.model_copy(update={"has_gloria": False})
    plan = BuildPlanner().plan(template, mass, one_deck_per_song(mass))
    assert all(s.tag.moment is not SongMoment.GLORIA for s in template_slides(template, plan))
    assert SongMoment.GLORIA.value not in song_moments(plan)


def test_blank_second_reading_removes_the_group(template: MassTemplate, mass_26tc: Mass) -> None:
    liturgy = mass_26tc.liturgy.model_copy(update={"second_reading": "  "})
    mass = mass_26tc.model_copy(update={"liturgy": liturgy})
    plan = BuildPlanner().plan(template, mass, one_deck_per_song(mass))
    assert all(s.tag.group != SECOND_READING_GROUP for s in template_slides(template, plan))


def test_song_without_pages_is_removed(template: MassTemplate, mass_26tc: Mass) -> None:
    decks = one_deck_per_song(mass_26tc)
    decks[SongMoment.MANTRA] = SongDeck(path=Path("/cache/mantra.pptx"), pages=0)
    plan = BuildPlanner().plan(template, mass_26tc, decks)
    assert all(s.tag.moment is not SongMoment.MANTRA for s in template_slides(template, plan))
    assert "mantra" not in song_moments(plan)


def test_prayer_missing_from_the_folder_is_an_error(tmp_path: Path, mass_26tc: Mass) -> None:
    folder = tmp_path / "oes"
    folder.mkdir()
    shutil.copy(default_prayers_dir() / "III.pptx", folder / "III.pptx")
    template = MassTemplate.load(prayers_dir=folder)
    liturgy = mass_26tc.liturgy.model_copy(update={"eucharistic_prayer": EucharisticPrayer.IV})
    mass = mass_26tc.model_copy(update={"liturgy": liturgy})
    with pytest.raises(TemplateError, match="Oração Eucarística IV"):
        BuildPlanner().plan(template, mass, one_deck_per_song(mass))


def test_plan_is_pure(template: MassTemplate, mass_26tc: Mass) -> None:
    decks = {SongMoment.MANTRA: SongDeck(path=Path("/cache/x.pptx"), pages=1)}
    first = BuildPlanner().plan(template, mass_26tc, decks)
    second = BuildPlanner().plan(template, mass_26tc, decks)
    assert first == second
