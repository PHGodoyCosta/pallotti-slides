"""Domain data contract (ARQUITETURA §4). Pure pydantic models, no I/O."""

import datetime as dt
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from .enums import (
    EucharisticPrayer,
    LiturgicalSeason,
    SongMoment,
    SongSource,
    StanzaType,
)


class Line(BaseModel):
    """One line of a stanza."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    bold: bool = False


class Stanza(BaseModel):
    """A stanza of a song; ``id`` is unique inside the song."""

    model_config = ConfigDict(extra="forbid")

    id: int
    type: StanzaType
    lines: list[Line]


class Song(BaseModel):
    """A song split in stanzas, with the execution order given by stanza ids."""

    model_config = ConfigDict(extra="forbid")

    title: str
    artist: str | None = None
    source: SongSource
    source_url: str | None = None
    stanzas: list[Stanza]
    order: list[int]

    @model_validator(mode="after")
    def _check_ids(self) -> Self:
        ids = [stanza.id for stanza in self.stanzas]
        if len(set(ids)) != len(ids):
            raise ValueError("os ids das estrofes devem ser únicos")
        unknown = sorted(set(self.order) - set(ids))
        if unknown:
            raise ValueError(f"a ordem cita estrofes inexistentes: {unknown}")
        return self

    def sequence(self) -> list[Stanza]:
        """Stanzas in execution order (a repeated id yields the same stanza again)."""
        by_id = {stanza.id: stanza for stanza in self.stanzas}
        return [by_id[stanza_id] for stanza_id in self.order]


class Celebration(BaseModel):
    """Identification of the celebration."""

    model_config = ConfigDict(extra="forbid")

    title: str  # already normalized, e.g. "30° Domingo do Tempo Comum"
    short_title: str | None = None  # None = rules.short_title_rule(title)
    date: dt.date
    season: LiturgicalSeason
    year: Literal["A", "B", "C"] | None = None


class Liturgy(BaseModel):
    """Liturgical texts that go into the template tags."""

    model_config = ConfigDict(extra="forbid")

    first_reading: str
    psalm_number: str
    psalm_refrain: str
    second_reading: str | None = None
    gospel: str
    intercessions_response: str
    eucharistic_prayer: EucharisticPrayer
    mystery_of_faith: str  # leaflet text (varies with rite/prayer); empty = error


class Mass(BaseModel):
    """Everything needed to generate the slides of one Mass."""

    model_config = ConfigDict(extra="forbid")

    celebration: Celebration
    liturgy: Liturgy
    has_gloria: bool
    songs: dict[SongMoment, Song]  # absent moment = no song


class SongRequest(BaseModel):
    """What the user typed for a song moment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    moment: SongMoment
    text: str
    kind: Literal["title", "url", "lyrics"]


class Notice(BaseModel):
    """A recoverable problem or remark (never an exception)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Literal["info", "warning", "error"]
    message: str
    field: str | None = None
