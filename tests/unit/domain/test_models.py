"""Domain models: validation, round trip and the reference fixture."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pallotti_slides.domain.enums import (
    EucharisticPrayer,
    LiturgicalSeason,
    SongMoment,
    SongSource,
    StanzaType,
)
from pallotti_slides.domain.models import Line, Mass, Song, Stanza

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "masses" / "26tc_2026.json"


def _song(order: list[int]) -> Song:
    return Song(
        title="Teste",
        source=SongSource.MANUAL,
        stanzas=[
            Stanza(id=1, type=StanzaType.VERSE, lines=[Line(text="verso")]),
            Stanza(id=2, type=StanzaType.CHORUS, lines=[Line(text="refrão", bold=True)]),
        ],
        order=order,
    )


def test_song_sequence_follows_order_and_repeats_stanzas() -> None:
    song = _song([1, 2, 1, 2])
    assert [stanza.id for stanza in song.sequence()] == [1, 2, 1, 2]
    assert song.sequence()[1] is song.sequence()[3]


def test_song_order_with_unknown_stanza_is_rejected() -> None:
    with pytest.raises(ValidationError, match="inexistentes"):
        _song([1, 3])


def test_song_duplicate_stanza_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="únicos"):
        Song(
            title="Teste",
            source=SongSource.MANUAL,
            stanzas=[
                Stanza(id=1, type=StanzaType.VERSE, lines=[]),
                Stanza(id=1, type=StanzaType.CHORUS, lines=[]),
            ],
            order=[1],
        )


def test_song_moment_declaration_order_and_labels() -> None:
    assert [moment.value for moment in SongMoment] == [
        "mantra",
        "entrance",
        "penitential_act",
        "gloria",
        "acclamation",
        "offertory",
        "communion",
        "post_communion",
        "recessional",
    ]
    assert SongMoment.ENTRANCE.label == "Canto de Entrada"
    assert SongMoment.PENITENTIAL_ACT.label == "Ato Penitencial"
    assert all(moment.label for moment in SongMoment)


def test_line_is_frozen() -> None:
    line = Line(text="x")
    with pytest.raises(ValidationError):
        line.text = "y"  # type: ignore[misc]


def test_reference_fixture_is_valid() -> None:
    mass = Mass.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    assert mass.celebration.title == "26° Domingo do Tempo Comum"
    assert mass.celebration.date.isoformat() == "2026-09-26"
    assert mass.celebration.season is LiturgicalSeason.ORDINARY_TIME
    assert mass.celebration.year is None
    assert mass.celebration.short_title is None
    assert mass.liturgy.eucharistic_prayer is EucharisticPrayer.III
    assert mass.liturgy.mystery_of_faith
    assert mass.has_gloria is True
    assert list(mass.songs) == [
        SongMoment.MANTRA,
        SongMoment.ENTRANCE,
        SongMoment.PENITENTIAL_ACT,
        SongMoment.GLORIA,
        SongMoment.ACCLAMATION,
        SongMoment.OFFERTORY,
    ]
    for song in mass.songs.values():
        assert song.sequence()
        assert all(stanza.lines for stanza in song.stanzas)
        assert all(
            (stanza.type is StanzaType.CHORUS) == all(line.bold for line in stanza.lines)
            for stanza in song.stanzas
        )


def test_reference_fixture_json_round_trip() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mass = Mass.model_validate(raw)
    assert mass.model_dump(mode="json") == raw
    assert Mass.model_validate_json(mass.model_dump_json()) == mass
