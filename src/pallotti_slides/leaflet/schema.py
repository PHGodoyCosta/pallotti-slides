"""Structured output schema for the leaflet extraction (ARQUITETURA §7)."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from pallotti_slides.domain.enums import EucharisticPrayer, LiturgicalSeason

# Fields the program needs; the second reading is legitimately absent on some days.
_REQUIRED_LABELS: dict[str, str] = {
    "title": "título da celebração",
    "first_reading": "1ª leitura",
    "psalm_number": "número do salmo",
    "psalm_refrain": "refrão do salmo",
    "gospel": "Evangelho",
    "intercessions_response": "refrão das preces",
    "eucharistic_prayer": "oração eucarística",
    "mystery_of_faith": "mistério da fé",
}


class LeafletData(BaseModel):
    """What the model found in the leaflet. Anything not found is ``None``."""

    title: str | None = Field(default=None, description="Ex.: 26º Domingo do Tempo Comum")
    date: dt.date | None = Field(default=None, description="Data da celebração impressa")
    season: LiturgicalSeason | None = None
    year: Literal["A", "B", "C"] | None = None
    first_reading: str | None = Field(default=None, description="Ex.: Ez 18,25-28")
    psalm_number: str | None = Field(default=None, description="Ex.: 24(25)")
    psalm_refrain: str | None = None
    second_reading: str | None = Field(default=None, description="Ex.: Fl 2,1-11")
    gospel: str | None = Field(default=None, description="Ex.: Mt 21,28-32")
    intercessions_response: str | None = None
    eucharistic_prayer: EucharisticPrayer | None = None
    mystery_of_faith: str | None = Field(
        default=None, description="Texto exato da aclamação, como impresso"
    )
    notes: list[str] = Field(default_factory=list, description="Observações e dúvidas")

    def is_empty(self) -> bool:
        """True when none of the key fields was found (not a leaflet)."""
        keys = [*_REQUIRED_LABELS, "second_reading", "date", "season", "year"]
        return all(getattr(self, key) in (None, "") for key in keys)

    def missing_fields(self) -> list[str]:
        """Portuguese labels of the required fields that came back empty."""
        return [label for key, label in _REQUIRED_LABELS.items() if not getattr(self, key)]
