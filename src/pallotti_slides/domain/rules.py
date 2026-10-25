"""Business rules (pure functions)."""

import datetime as dt
import re

from .enums import LiturgicalSeason
from .models import Mass, Notice

_SUNDAY = 6  # datetime.weekday()
_INVALID_FILE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

_REQUIRED_TEXTS: list[tuple[str, str, str]] = [
    # (field path, attribute owner, message)
    ("celebration.title", "celebration", "Informe o título da celebração."),
    ("liturgy.first_reading", "liturgy", "Informe a referência da 1ª leitura."),
    ("liturgy.psalm_number", "liturgy", "Informe o número do salmo."),
    ("liturgy.psalm_refrain", "liturgy", "Informe o refrão do salmo."),
    ("liturgy.gospel", "liturgy", "Informe a referência do Evangelho."),
    ("liturgy.intercessions_response", "liturgy", "Informe o refrão das preces."),
    (
        "liturgy.mystery_of_faith",
        "liturgy",
        "Informe a aclamação do mistério da fé (texto do folheto).",
    ),
]


def default_has_gloria(season: LiturgicalSeason) -> bool:
    """The Gloria is not sung in Advent and Lent."""
    return season not in {LiturgicalSeason.ADVENT, LiturgicalSeason.LENT}


def validate_mass(mass: Mass) -> list[Notice]:
    """Errors for every required field that is empty."""
    notices: list[Notice] = []
    for field, owner, message in _REQUIRED_TEXTS:
        value = getattr(getattr(mass, owner), field.split(".", 1)[1])
        if not value.strip():
            notices.append(Notice(level="error", message=message, field=field))
    return notices


def short_title_rule(title: str) -> str:
    """ "Domingo" -> "Dom" and "do Tempo Comum" -> "do T.C"; the rest is kept."""
    shortened = re.sub(r"\bdo Tempo Comum\b", "do T.C", title)
    return re.sub(r"\bDomingo\b", "Dom", shortened)


def output_file_name(mass: Mass) -> str:
    """File name without extension: "Missa - 26° Dom do T.C - 26.09.2026 - OE III"."""
    celebration = mass.celebration
    short_title = (celebration.short_title or "").strip() or short_title_rule(celebration.title)
    short_title = " ".join(_INVALID_FILE_CHARS.sub(" ", short_title).split())
    date_text = celebration.date.strftime("%d.%m.%Y")
    prayer = mass.liturgy.eucharistic_prayer.value
    return f"Missa - {short_title} - {date_text} - OE {prayer}"


def next_sunday(today: dt.date) -> dt.date:
    """Default date of a new Mass: today if it is Sunday, else the next Sunday."""
    return today + dt.timedelta(days=(_SUNDAY - today.weekday()) % 7)
