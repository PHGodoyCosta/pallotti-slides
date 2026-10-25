"""SongRepository methods behind the library: usage, alias removal and merge."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from pallotti_slides.db.repositories import (
    MassRepository,
    NotFoundError,
    SongRepository,
    SongUsage,
)
from pallotti_slides.db.session import apply_migrations, make_engine, session_factory
from pallotti_slides.domain.enums import SongMoment, SongSource, StanzaType
from pallotti_slides.domain.models import Line, Mass, Song, Stanza
from pallotti_slides.domain.text import normalize_search

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "masses" / "26tc_2026.json"


def make_song(title: str, url: str | None = None) -> Song:
    return Song(
        title=title,
        source=SongSource.MANUAL,
        source_url=url,
        stanzas=[Stanza(id=1, type=StanzaType.VERSE, lines=[Line(text=f"Verso de {title}")])],
        order=[1],
    )


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    apply_migrations(engine)
    with session_factory(engine)() as s:
        yield s
    engine.dispose()


def test_usage_counts_masses_and_last_date(session: Session) -> None:
    mass = Mass.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    songs = SongRepository(session)
    _, song = next(iter(mass.songs.items()))
    song_id = songs.add(song, "letra")
    other_id = songs.add(make_song("Nunca usado"), "x")
    masses = MassRepository(session)
    masses.save(mass)
    later = mass.model_copy(deep=True)
    later.celebration.date = mass.celebration.date.replace(year=mass.celebration.date.year + 1)
    masses.save(later)

    usage = songs.usage(song_id)
    assert usage.count >= 2
    assert usage.last_date == later.celebration.date
    assert songs.usage(other_id) == SongUsage()
    assert songs.usage_all()[song_id] == usage
    with pytest.raises(NotFoundError):
        songs.usage(999)


def test_remove_alias(session: Session) -> None:
    songs = SongRepository(session)
    first = songs.add(make_song("Um"), "a")
    songs.add_alias(first, "Primeiro")
    songs.add_alias(first, "Segundo")
    songs.remove_alias(first, "PRIMEIRO")
    assert songs.aliases(first) == ["segundo"]
    songs.remove_alias(first, "inexistente")  # no error
    with pytest.raises(NotFoundError):
        songs.remove_alias(999, "x")


def test_merge_moves_everything_and_deletes_dropped(session: Session) -> None:
    mass = Mass.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    songs = SongRepository(session)
    _, mass_song = next(iter(mass.songs.items()))
    drop = songs.add(mass_song, "d", usual_moments=[SongMoment.ENTRANCE, SongMoment.COMMUNION])
    keep = songs.add(make_song("Canto Principal"), "k", usual_moments=[SongMoment.ENTRANCE])
    songs.add_alias(drop, "apelido do descartado")
    songs.add_alias(keep, "apelido do principal")
    mass_id = MassRepository(session).save(mass)

    songs.merge(keep, drop)

    assert songs.get(drop) is None
    record = songs.record(keep)
    assert {"apelido do principal", "apelido do descartado"} <= set(record.aliases)
    assert normalize_search(mass_song.title) in record.aliases
    assert len(record.aliases) == 3
    assert record.usual_moments == [SongMoment.ENTRANCE, SongMoment.COMMUNION]
    linked = (
        session.execute(
            text(
                "SELECT DISTINCT song_id FROM mass_songs WHERE mass_id=:m AND song_id IS NOT NULL"
            ),
            {"m": mass_id},
        )
        .scalars()
        .all()
    )
    assert keep in linked
    assert drop not in linked
    assert songs.usage(keep).count >= 1


def test_merge_is_atomic_on_failure(session: Session) -> None:
    songs = SongRepository(session)
    keep = songs.add(make_song("A"), "a")
    with pytest.raises(NotFoundError):
        songs.merge(keep, 999)
    assert songs.get(keep) is not None
    with pytest.raises(ValueError, match="diferentes"):
        songs.merge(keep, keep)
