"""SongPaginator: one page per stanza, balanced splits, one size per song (SPEC F9)."""

from collections.abc import Sequence

import pytest

from pallotti_slides.config import TypographyConfig
from pallotti_slides.domain.enums import SongMoment, SongSource, StanzaType
from pallotti_slides.domain.models import Line, Mass, Song, Stanza
from pallotti_slides.presentation.measurer import BodyFormat, Box, TextMeasurer
from pallotti_slides.presentation.paginator import SongPaginator, split_balanced
from pallotti_slides.presentation.template import MassTemplate

BOX = Box(0, 0, 10_000_000, 5_000_000)


class FakeMeasurer:
    """A page fits when ``len(lines) * size <= budget`` (no fonts involved)."""

    def __init__(self, budget: float) -> None:
        self.budget = budget
        self.notices: list[object] = []

    def fits(
        self, lines: Sequence[Line], size_pt: float, box: Box, body: BodyFormat | None = None
    ) -> bool:
        return len(lines) * size_pt <= self.budget


def lines(count: int, prefix: str = "Linha de teste", bold: bool = False) -> list[Line]:
    return [Line(text=f"{prefix} {n}", bold=bold) for n in range(1, count + 1)]


def song(*stanzas: list[Line], order: list[int] | None = None) -> Song:
    return Song(
        title="Teste",
        source=SongSource.MANUAL,
        stanzas=[
            Stanza(id=i, type=StanzaType.VERSE, lines=stanza_lines)
            for i, stanza_lines in enumerate(stanzas, start=1)
        ],
        order=order or list(range(1, len(stanzas) + 1)),
    )


def paginator(budget: float, config: TypographyConfig | None = None) -> SongPaginator:
    return SongPaginator(FakeMeasurer(budget), config)  # type: ignore[arg-type]


def test_split_balanced() -> None:
    assert [len(c) for c in split_balanced(lines(12), 2)] == [6, 6]
    assert [len(c) for c in split_balanced(lines(7), 2)] == [4, 3]
    assert [len(c) for c in split_balanced(lines(13), 3)] == [5, 4, 4]
    assert [len(c) for c in split_balanced(lines(2), 5)] == [1, 1]


def test_one_page_per_stanza_in_execution_order_with_repeated_chorus() -> None:
    chorus = lines(4, "Refrão", bold=True)
    pages = paginator(1000).paginate(
        song(lines(4, "A"), chorus, lines(4, "B"), order=[1, 2, 3, 2]), BOX
    )
    assert [p.lines[0].text for p in pages] == ["A 1", "Refrão 1", "B 1", "Refrão 1"]
    assert all(p.lines[0].bold for p in pages if p.lines[0].text.startswith("Refrão"))


def test_largest_size_where_every_page_fits_for_the_whole_song() -> None:
    # 5 lines * 50 = 250 > 240 (no); 5 * 48 = 240 (yes) -> 48 for every page, even the short one.
    pages = paginator(240).paginate(song(lines(2), lines(5)), BOX)
    assert [p.size_pt for p in pages] == [48, 48]


def test_max_font_when_everything_fits() -> None:
    pages = paginator(10_000).paginate(song(lines(3)), BOX)
    assert [p.size_pt for p in pages] == [54]


def test_twelve_lines_become_two_pages_of_six() -> None:
    pages = paginator(10_000).paginate(song(lines(12)), BOX)
    assert [len(p.lines) for p in pages] == [6, 6]
    assert [line.text for p in pages for line in p.lines] == [line.text for line in lines(12)]


def test_split_again_when_nothing_fits_in_min_font() -> None:
    # 6 lines never fit (6 * 40 = 240 > 200); 3 lines fit at 54 (162 <= 200).
    pages = paginator(200).paginate(song(lines(6)), BOX)
    assert [len(p.lines) for p in pages] == [3, 3]
    assert {p.size_pt for p in pages} == {54}


def test_a_single_line_that_never_fits_stays_in_min_font() -> None:
    pages = paginator(10).paginate(song(lines(1)), BOX)
    assert [(len(p.lines), p.size_pt) for p in pages] == [(1, 40)]


def test_config_is_respected() -> None:
    config = TypographyConfig(min_font=30, max_font=36, max_lines=4)
    pages = paginator(10_000, config).paginate(song(lines(8)), BOX)
    assert [(len(p.lines), p.size_pt) for p in pages] == [(4, 36), (4, 36)]


def test_empty_song_has_no_pages() -> None:
    assert paginator(1000).paginate(song([]), BOX) == []


def test_invalid_config_is_rejected() -> None:
    with pytest.raises(ValueError):
        TypographyConfig(min_font=50, max_font=40)


def test_real_measurer_twelve_line_stanza(
    measurer: TextMeasurer, template: MassTemplate, mass_full: Mass
) -> None:
    moment = SongMoment.COMMUNION
    pages = SongPaginator(measurer).paginate(
        mass_full.songs[moment], template.song_area(moment), template.body_format(moment)
    )
    assert [len(p.lines) for p in pages[:2]] == [6, 6]
    assert [p.lines[0].text for p in pages[:2]] == ["Linha de teste 1", "Linha de teste 7"]
    assert len({p.size_pt for p in pages}) == 1


def test_real_measurer_sizes_of_the_reference_mass(
    measurer: TextMeasurer, template: MassTemplate, mass_26tc: Mass
) -> None:
    paginator_ = SongPaginator(measurer)
    sizes = {}
    for moment, item in mass_26tc.songs.items():
        area, body = template.song_area(moment), template.body_format(moment)
        pages = paginator_.paginate(item, area, body)
        assert len(pages) == len(item.order)  # no stanza of the example needs splitting
        assert all(measurer.fits(p.lines, p.size_pt, area, body) for p in pages)
        sizes[moment] = pages[0].size_pt
    assert all(40 <= size <= 54 and size % 2 == 0 for size in sizes.values())
    assert sizes[SongMoment.MANTRA] == 54
