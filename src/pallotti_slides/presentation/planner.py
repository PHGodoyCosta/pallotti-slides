"""Build plan: which slides go into the deck, from which file, in which order, with which texts.

Pure function of (template, Mass, song decks): no I/O, no XML (ARQUITETURA §5). The slides come
from the template, from the chosen prayer block (``<prayers_dir>/<id>.pptx``, in place of the
``@pallotti oe=slot`` marker) and from the cached song decks (``SongDeckCache``, in place of
each song prototype).
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import Line, Mass
from pallotti_slides.presentation.errors import TemplateError
from pallotti_slides.presentation.song_cache import SongDeck
from pallotti_slides.presentation.template import (
    SECOND_READING_GROUP,
    SONG_LABEL_FIELD,
    SONG_TEXT_FIELD,
    MassTemplate,
    TagKind,
    TemplateSlide,
)


@dataclass(frozen=True)
class TextContent:
    """New content of a ``{{...}}`` tag.

    Plain fields replace the tag inside its run (``text``). The song body (``song.text``)
    becomes one paragraph per line (``lines``), all in ``size_pt``.
    """

    text: str = ""
    lines: tuple[Line, ...] = ()
    size_pt: int | None = None

    @property
    def is_body(self) -> bool:
        return self.size_pt is not None


@dataclass(frozen=True)
class TargetSlide:
    """One slide of the generated deck: a copy of slide ``source`` (0-based) of ``deck``.

    ``deck`` is ``None`` for the template itself, or the path of another .pptx (prayer block,
    cached song deck) whose slide is imported.
    """

    source: int
    replacements: dict[str, TextContent] = field(default_factory=dict)
    deck: Path | None = None


@dataclass(frozen=True)
class SlidePlan:
    """Ordered list of the slides of the generated deck."""

    slides: list[TargetSlide]

    def __iter__(self) -> Iterator[TargetSlide]:
        return iter(self.slides)

    def __len__(self) -> int:
        return len(self.slides)

    @property
    def sources(self) -> list[int]:
        return [slide.source for slide in self.slides]


def _plain_values(mass: Mass) -> dict[str, str]:
    values = {"celebration.title": mass.celebration.title}
    for name, value in mass.liturgy.model_dump(mode="json").items():
        values[f"liturgy.{name}"] = value if isinstance(value, str) else ""
    return values


class BuildPlanner:
    """Decides the slides of the deck (SPEC F8): groups, Eucharistic prayer and song pages."""

    def plan(
        self,
        template: MassTemplate,
        mass: Mass,
        songs: Mapping[SongMoment, SongDeck],
    ) -> SlidePlan:
        block = template.prayer_block(mass.liturgy.eucharistic_prayer)
        if template.prayer_slot() is None:
            raise TemplateError(
                "O modelo não tem o slide marcador da Oração Eucarística (@pallotti oe=slot)."
            )
        active = {
            moment
            for moment, deck in songs.items()
            if deck.pages > 0 and (moment is not SongMoment.GLORIA or mass.has_gloria)
        }
        has_second_reading = bool((mass.liturgy.second_reading or "").strip())
        values = _plain_values(mass)

        targets: list[TargetSlide] = []
        for slide in template.slides:
            kind = slide.tag.kind
            if kind in (TagKind.INVALID, TagKind.PRAYER):
                raise TemplateError(
                    f"Etiqueta inválida no slide {slide.index + 1} do modelo: {slide.tag.raw!r}."
                )
            moment = slide.tag.moment
            if kind is TagKind.SONG:
                if moment is not None and moment in active:
                    targets.extend(self._song_slides(slide, moment, songs[moment], values))
                continue
            if kind is TagKind.PRAYER_SLOT:
                targets.extend(
                    TargetSlide(s.index, self._plain(s, values), deck=block.path)
                    for s in block.slides
                )
                continue
            if kind is TagKind.GROUP:
                if slide.tag.group == SECOND_READING_GROUP and not has_second_reading:
                    continue
                if moment is not None and moment not in active:
                    continue
            targets.append(TargetSlide(slide.index, self._plain(slide, values)))
        return SlidePlan(targets)

    @staticmethod
    def _plain(
        slide: TemplateSlide, values: Mapping[str, str], skip: frozenset[str] = frozenset()
    ) -> dict[str, TextContent]:
        replacements: dict[str, TextContent] = {}
        for name in sorted(slide.fields - skip):
            if name not in values:
                raise TemplateError(
                    f"Etiqueta do campo {name!r} fora de lugar no slide {slide.index + 1}."
                )
            replacements[name] = TextContent(text=values[name])
        return replacements

    def _song_slides(
        self,
        slide: TemplateSlide,
        moment: SongMoment,
        deck: SongDeck,
        values: Mapping[str, str],
    ) -> list[TargetSlide]:
        """One slide per page of the cached deck; only the label (and plain fields) change."""
        others = self._plain(slide, values, skip=frozenset({SONG_LABEL_FIELD, SONG_TEXT_FIELD}))
        replacements = {**others, SONG_LABEL_FIELD: TextContent(text=moment.label)}
        return [TargetSlide(page, dict(replacements), deck=deck.path) for page in range(deck.pages)]
