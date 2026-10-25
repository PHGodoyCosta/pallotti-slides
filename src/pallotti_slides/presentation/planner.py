"""Build plan: which template slides go into the deck, in which order, with which texts.

Pure function of (template, Mass, song pages): no I/O, no XML (ARQUITETURA §5).
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import Line, Mass
from pallotti_slides.presentation.errors import TemplateError
from pallotti_slides.presentation.paginator import SongPage
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
    """One slide of the generated deck: a copy of template slide ``source`` (0-based)."""

    source: int
    replacements: dict[str, TextContent] = field(default_factory=dict)


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
        pages: Mapping[SongMoment, list[SongPage]],
    ) -> SlidePlan:
        prayer = mass.liturgy.eucharistic_prayer
        if prayer not in template.available_prayers():
            raise TemplateError(
                f"O modelo não tem o bloco da Oração Eucarística {prayer.value} (@pallotti oe=...)."
            )
        active = {
            moment
            for moment, song_pages in pages.items()
            if song_pages and (moment is not SongMoment.GLORIA or mass.has_gloria)
        }
        has_second_reading = bool((mass.liturgy.second_reading or "").strip())
        values = _plain_values(mass)

        targets: list[TargetSlide] = []
        for slide in template.slides:
            kind = slide.tag.kind
            if kind is TagKind.INVALID:
                raise TemplateError(
                    f"Etiqueta inválida no slide {slide.index + 1} do modelo: {slide.tag.raw!r}."
                )
            moment = slide.tag.moment
            if kind is TagKind.SONG:
                if moment is not None and moment in active:
                    targets.extend(self._song_slides(slide, moment, pages[moment], values))
                continue
            if kind is TagKind.PRAYER and slide.tag.prayer is not prayer:
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
        song_pages: list[SongPage],
        values: Mapping[str, str],
    ) -> list[TargetSlide]:
        others = self._plain(slide, values, skip=frozenset({SONG_LABEL_FIELD, SONG_TEXT_FIELD}))
        return [
            TargetSlide(
                slide.index,
                {
                    **others,
                    SONG_LABEL_FIELD: TextContent(text=moment.label),
                    SONG_TEXT_FIELD: TextContent(lines=tuple(page.lines), size_pt=page.size_pt),
                },
            )
            for page in song_pages
        ]
