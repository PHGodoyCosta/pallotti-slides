"""BuildPlanner: which template slides go into the deck and with which texts (SPEC F8)."""

import pytest

from pallotti_slides.domain.enums import EucharisticPrayer, SongMoment
from pallotti_slides.domain.models import Line, Mass
from pallotti_slides.presentation.errors import TemplateError
from pallotti_slides.presentation.paginator import SongPage
from pallotti_slides.presentation.planner import BuildPlanner, SlidePlan, TextContent
from pallotti_slides.presentation.template import (
    SECOND_READING_GROUP,
    MassTemplate,
    TagKind,
    TemplateSlide,
)


def one_page_per_stanza(mass: Mass) -> dict[SongMoment, list[SongPage]]:
    return {
        moment: [SongPage(lines=list(s.lines), size_pt=48) for s in song.sequence()]
        for moment, song in mass.songs.items()
    }


def kinds(template: MassTemplate, plan: SlidePlan) -> list[TemplateSlide]:
    return [template.slides[source] for source in plan.sources]


def test_reference_mass_keeps_all_but_the_absent_songs(
    template: MassTemplate, mass_26tc: Mass
) -> None:
    plan = BuildPlanner().plan(template, mass_26tc, one_page_per_stanza(mass_26tc))
    absent = {SongMoment.COMMUNION, SongMoment.POST_COMMUNION, SongMoment.RECESSIONAL}
    removed = [s for s in template.slides if s.index not in set(plan.sources)]
    songs_removed = [s for s in removed if s.tag.prayer is None]
    assert {s.tag.moment for s in songs_removed} == absent
    assert len(songs_removed) == 6  # separator + prototype of each absent moment
    # the other prayer block (DC IV: 9 images + 9 responses) is removed too
    assert len(removed) - len(songs_removed) == 18
    assert len(plan) == 69


def test_prototype_is_repeated_once_per_page_with_label_and_body(
    template: MassTemplate, mass_26tc: Mass
) -> None:
    pages = one_page_per_stanza(mass_26tc)
    plan = BuildPlanner().plan(template, mass_26tc, pages)
    prototype = template.prototype(SongMoment.ENTRANCE)
    assert prototype is not None
    targets = [t for t in plan if t.source == prototype.index]
    assert len(targets) == 4  # order [1, 2, 3, 2]
    sources = plan.sources
    first = sources.index(prototype.index)
    assert sources[first : first + 4] == [prototype.index] * 4
    for target, page in zip(targets, pages[SongMoment.ENTRANCE], strict=True):
        assert target.replacements["song.label"] == TextContent(text="Canto de Entrada")
        body = target.replacements["song.text"]
        assert body.is_body
        assert list(body.lines) == page.lines
        assert body.size_pt == 48


def test_every_field_of_every_slide_gets_a_value(template: MassTemplate, mass_26tc: Mass) -> None:
    plan = BuildPlanner().plan(template, mass_26tc, one_page_per_stanza(mass_26tc))
    for target in plan:
        assert set(target.replacements) == template.slides[target.source].fields
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
    plan = BuildPlanner().plan(template, mass_full, one_page_per_stanza(mass_full))
    slides = kinds(template, plan)
    assert all(s.tag.moment is not SongMoment.GLORIA for s in slides)
    assert all(s.tag.group != SECOND_READING_GROUP for s in slides)
    song_order = []
    for slide in slides:
        moment = slide.tag.moment
        if slide.tag.kind is TagKind.SONG and moment is not None and moment not in song_order:
            song_order.append(moment)
    expected = [m for m in SongMoment if m is not SongMoment.GLORIA]
    assert song_order == expected


def test_has_gloria_false_removes_gloria_even_with_a_song(
    template: MassTemplate, mass_26tc: Mass
) -> None:
    mass = mass_26tc.model_copy(update={"has_gloria": False})
    plan = BuildPlanner().plan(template, mass, one_page_per_stanza(mass))
    assert all(s.tag.moment is not SongMoment.GLORIA for s in kinds(template, plan))


def test_blank_second_reading_removes_the_group(template: MassTemplate, mass_26tc: Mass) -> None:
    liturgy = mass_26tc.liturgy.model_copy(update={"second_reading": "  "})
    mass = mass_26tc.model_copy(update={"liturgy": liturgy})
    plan = BuildPlanner().plan(template, mass, one_page_per_stanza(mass))
    assert all(s.tag.group != SECOND_READING_GROUP for s in kinds(template, plan))


def test_song_without_pages_is_removed(template: MassTemplate, mass_26tc: Mass) -> None:
    pages = one_page_per_stanza(mass_26tc)
    pages[SongMoment.MANTRA] = []
    plan = BuildPlanner().plan(template, mass_26tc, pages)
    assert all(s.tag.moment is not SongMoment.MANTRA for s in kinds(template, plan))


def test_only_the_chosen_prayer_block_stays(template: MassTemplate, mass_26tc: Mass) -> None:
    plan = BuildPlanner().plan(template, mass_26tc, one_page_per_stanza(mass_26tc))
    block = [s for s in template.slides if s.tag.prayer is EucharisticPrayer.III]
    assert all(s.index in plan.sources for s in block)


def test_prayer_missing_from_the_template_is_an_error(
    template: MassTemplate, mass_26tc: Mass
) -> None:
    liturgy = mass_26tc.liturgy.model_copy(update={"eucharistic_prayer": EucharisticPrayer.II})
    mass = mass_26tc.model_copy(update={"liturgy": liturgy})
    with pytest.raises(TemplateError, match="Oração Eucarística II"):
        BuildPlanner().plan(template, mass, one_page_per_stanza(mass))


def test_plan_is_pure(template: MassTemplate, mass_26tc: Mass) -> None:
    pages = {SongMoment.MANTRA: [SongPage(lines=[Line(text="x")], size_pt=40)]}
    first = BuildPlanner().plan(template, mass_26tc, pages)
    second = BuildPlanner().plan(template, mass_26tc, pages)
    assert first == second
