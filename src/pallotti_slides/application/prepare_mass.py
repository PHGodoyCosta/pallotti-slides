"""Use case: prepare a Mass draft from date, leaflet and song requests (SPEC F1, F2, F4)."""

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pallotti_slides.domain.enums import EucharisticPrayer, LiturgicalSeason, SongMoment, SongSource
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import (
    Celebration,
    Liturgy,
    Mass,
    Notice,
    Song,
    SongRequest,
)
from pallotti_slides.domain.rules import default_has_gloria
from pallotti_slides.leaflet.schema import LeafletData
from pallotti_slides.songs.downloaders import RawLyrics
from pallotti_slides.songs.parser import LyricsParser

__all__ = [
    "LeafletExtractorLike",
    "LyricsOnlyResolver",
    "MassDraft",
    "MassPreparer",
    "SongResolution",
    "SongResolverLike",
]


class LeafletExtractorLike(Protocol):
    """Anything that turns a leaflet PDF into ``LeafletData`` (``LeafletExtractor``)."""

    def extract(self, pdf: Path) -> LeafletData: ...


@dataclass(frozen=True)
class SongResolution:
    """Outcome of resolving one request; ``song`` is ``None`` when it failed."""

    song: Song | None
    origin: str  # "pasted" | "library" | "web" | "none"
    notices: list[Notice] = field(default_factory=list)


class SongResolverLike(Protocol):
    """Resolves a ``SongRequest`` into a song (the real resolver arrives in M7)."""

    def resolve(self, request: SongRequest) -> SongResolution: ...


class LyricsOnlyResolver:
    """Provisional resolver: handles only pasted lyrics (``kind="lyrics"``)."""

    def __init__(self, parser: LyricsParser) -> None:
        self._parser = parser

    def resolve(self, request: SongRequest) -> SongResolution:
        field_name = f"songs.{request.moment.value}"
        if request.kind != "lyrics":
            return SongResolution(
                song=None,
                origin="none",
                notices=[
                    Notice(
                        level="warning",
                        message=(
                            f"Canto de {request.moment.label}: a busca por título ou link "
                            "estará disponível no M7. Cole a letra por enquanto."
                        ),
                        field=field_name,
                    )
                ],
            )
        raw = RawLyrics(title=request.moment.label, text=request.text, source=SongSource.MANUAL)
        song, notices = self._parser.parse(raw)
        scoped = [n.model_copy(update={"field": n.field or field_name}) for n in notices]
        return SongResolution(song=song, origin="pasted", notices=scoped)


@dataclass(frozen=True)
class MassDraft:
    """Partial Mass: date, leaflet data, resolved songs and everything that went wrong."""

    date: dt.date
    leaflet: LeafletData | None
    resolutions: dict[SongMoment, SongResolution]
    notices: list[Notice]

    @property
    def songs(self) -> dict[SongMoment, Song]:
        return {m: r.song for m, r in self.resolutions.items() if r.song is not None}

    def to_mass(self, eucharistic_prayer: EucharisticPrayer | None = None) -> Mass:
        """Build the ``Mass``; missing texts stay empty (``validate_mass`` reports them).

        The Eucharistic Prayer has no safe default: it must come from the leaflet or the caller.
        """
        data = self.leaflet or LeafletData()
        prayer = eucharistic_prayer or data.eucharistic_prayer
        if prayer is None:
            raise PallottiError("Informe a Oração Eucarística antes de montar a missa.")
        season = data.season or LiturgicalSeason.ORDINARY_TIME
        return Mass(
            celebration=Celebration(
                title=data.title or "",
                date=self.date,
                season=season,
                year=data.year,
            ),
            liturgy=Liturgy(
                first_reading=data.first_reading or "",
                psalm_number=data.psalm_number or "",
                psalm_refrain=data.psalm_refrain or "",
                second_reading=data.second_reading,
                gospel=data.gospel or "",
                intercessions_response=data.intercessions_response or "",
                eucharistic_prayer=prayer,
                mystery_of_faith=data.mystery_of_faith or "",
            ),
            has_gloria=default_has_gloria(season),
            songs=self.songs,
        )


class MassPreparer:
    """Leaflet extraction + song resolution; each stage fails on its own."""

    def __init__(self, extractor: LeafletExtractorLike, resolver: SongResolverLike) -> None:
        self._extractor = extractor
        self._resolver = resolver

    def prepare(
        self,
        date: dt.date,
        leaflet: Path | None,
        requests: list[SongRequest],
        free_text: str | None = None,
    ) -> MassDraft:
        notices: list[Notice] = []
        data: LeafletData | None = None
        if leaflet is not None:
            try:
                data = self._extractor.extract(leaflet)
            except PallottiError as error:
                notices.append(Notice(level="error", message=str(error), field="leaflet"))
            else:
                notices.extend(
                    Notice(
                        level="warning",
                        message=f"Não encontrei no folheto: {label}.",
                        field=label,
                    )
                    for label in data.missing_fields()
                )
                notices.extend(Notice(level="info", message=note) for note in data.notes)
                if data.date is not None and data.date != date:
                    notices.append(
                        Notice(
                            level="warning",
                            message=(
                                f"A data do folheto ({data.date:%d/%m/%Y}) é diferente da "
                                f"data informada ({date:%d/%m/%Y})."
                            ),
                            field="date",
                        )
                    )
        if free_text and free_text.strip():
            notices.append(
                Notice(
                    level="info",
                    message="O texto livre ainda não é interpretado (disponível no M7).",
                    field="free_text",
                )
            )

        resolutions: dict[SongMoment, SongResolution] = {}
        for request in requests:
            try:
                resolution = self._resolver.resolve(request)
            except PallottiError as error:
                resolution = SongResolution(
                    song=None,
                    origin="none",
                    notices=[
                        Notice(
                            level="error",
                            message=str(error),
                            field=f"songs.{request.moment.value}",
                        )
                    ],
                )
            resolutions[request.moment] = resolution
            notices.extend(resolution.notices)
        return MassDraft(date=date, leaflet=data, resolutions=resolutions, notices=notices)
