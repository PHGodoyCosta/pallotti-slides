"""Domain rules: gloria default, validation, file name, short title, next Sunday."""

import datetime as dt
from pathlib import Path

import pytest

from pallotti_slides.domain.enums import LiturgicalSeason
from pallotti_slides.domain.models import Mass
from pallotti_slides.domain.rules import (
    default_has_gloria,
    next_sunday,
    output_file_name,
    short_title_rule,
    validate_mass,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "masses" / "26tc_2026.json"
EXAMPLE_STEM = "Missa - 26° Dom do T.C - 26.09.2026 - OE III"


@pytest.fixture
def mass() -> Mass:
    return Mass.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("season", list(LiturgicalSeason))
def test_default_has_gloria_only_false_in_advent_and_lent(season: LiturgicalSeason) -> None:
    expected = season not in {LiturgicalSeason.ADVENT, LiturgicalSeason.LENT}
    assert default_has_gloria(season) is expected


def test_validate_mass_accepts_the_reference_fixture(mass: Mass) -> None:
    assert validate_mass(mass) == []


def test_validate_mass_allows_missing_second_reading(mass: Mass) -> None:
    mass.liturgy.second_reading = None
    assert validate_mass(mass) == []


@pytest.mark.parametrize(
    "field",
    [
        "celebration.title",
        "liturgy.first_reading",
        "liturgy.psalm_number",
        "liturgy.psalm_refrain",
        "liturgy.gospel",
        "liturgy.intercessions_response",
        "liturgy.mystery_of_faith",
    ],
)
@pytest.mark.parametrize("empty", ["", "   "])
def test_validate_mass_reports_each_missing_field(mass: Mass, field: str, empty: str) -> None:
    owner, attribute = field.split(".")
    setattr(getattr(mass, owner), attribute, empty)
    notices = validate_mass(mass)
    assert [(n.level, n.field) for n in notices] == [("error", field)]
    assert notices[0].message


def test_validate_mass_reports_all_missing_fields_at_once(mass: Mass) -> None:
    mass.liturgy.gospel = ""
    mass.liturgy.mystery_of_faith = ""
    assert [n.field for n in validate_mass(mass)] == [
        "liturgy.gospel",
        "liturgy.mystery_of_faith",
    ]


def test_output_file_name_matches_the_example_without_short_title(mass: Mass) -> None:
    assert mass.celebration.short_title is None
    assert output_file_name(mass) == EXAMPLE_STEM


def test_output_file_name_matches_the_example_with_short_title(mass: Mass) -> None:
    mass.celebration.short_title = "26° Dom do T.C"
    assert output_file_name(mass) == EXAMPLE_STEM


def test_output_file_name_uses_custom_short_title_and_prayer(mass: Mass) -> None:
    mass.celebration.short_title = "Cristo Rei"
    mass.liturgy.eucharistic_prayer = type(mass.liturgy.eucharistic_prayer)("II")
    assert output_file_name(mass) == "Missa - Cristo Rei - 26.09.2026 - OE II"


def test_output_file_name_blank_short_title_falls_back_to_rule(mass: Mass) -> None:
    mass.celebration.short_title = "  "
    assert output_file_name(mass) == EXAMPLE_STEM


def test_output_file_name_removes_characters_invalid_in_file_names(mass: Mass) -> None:
    mass.celebration.short_title = "Natal: Missa/Dia"
    assert output_file_name(mass) == "Missa - Natal Missa Dia - 26.09.2026 - OE III"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("26° Domingo do Tempo Comum", "26° Dom do T.C"),
        ("2° Domingo da Páscoa", "2° Dom da Páscoa"),
        ("Natal do Senhor", "Natal do Senhor"),
        ("Domingo de Ramos", "Dom de Ramos"),
        ("Domingos", "Domingos"),
    ],
)
def test_short_title_rule(title: str, expected: str) -> None:
    assert short_title_rule(title) == expected


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (dt.date(2026, 9, 20), dt.date(2026, 9, 20)),  # Sunday -> same day
        (dt.date(2026, 9, 21), dt.date(2026, 9, 27)),  # Monday
        (dt.date(2026, 9, 26), dt.date(2026, 9, 27)),  # Saturday
        (dt.date(2026, 12, 28), dt.date(2027, 1, 3)),  # year change
    ],
)
def test_next_sunday(today: dt.date, expected: dt.date) -> None:
    result = next_sunday(today)
    assert result == expected
    assert result.weekday() == 6
