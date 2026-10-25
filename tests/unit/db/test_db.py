"""Database tests: SQLite file in tmp_path, no network."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from pallotti_slides.config import DB_URL_VAR, Paths, default_db_url
from pallotti_slides.db.repositories import (
    DuplicateError,
    MassFiles,
    MassRepository,
    NotFoundError,
    SongRepository,
)
from pallotti_slides.db.session import apply_migrations, make_engine, session_factory
from pallotti_slides.domain.enums import SongMoment, SongSource, StanzaType
from pallotti_slides.domain.models import Line, Mass, Song, Stanza

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "masses" / "26tc_2026.json"


def make_song(
    title: str = "Me chamaste para caminhar",
    first_line: str = "Me chamaste para caminhar",
    url: str | None = "https://www.letras.mus.br/x/1/",
) -> Song:
    return Song(
        title=title,
        artist="Autor",
        source=SongSource.LETRAS_MUS,
        source_url=url,
        stanzas=[
            Stanza(id=1, type=StanzaType.VERSE, lines=[Line(text=first_line), Line(text="outra")]),
            Stanza(id=2, type=StanzaType.CHORUS, lines=[Line(text="Refrão", bold=True)]),
        ],
        order=[1, 2, 1],
    )


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'sub' / 'test.db'}")
    apply_migrations(engine)
    with session_factory(engine)() as s:
        yield s
    engine.dispose()


def test_migrations_create_tables(session: Session) -> None:
    names = set(inspect(session.get_bind()).get_table_names())
    assert {"songs", "song_aliases", "masses", "mass_songs"} <= names


def test_apply_migrations_is_idempotent(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'a.db'}")
    apply_migrations(engine)
    apply_migrations(engine)
    engine.dispose()


def test_song_crud(session: Session) -> None:
    repo = SongRepository(session)
    song = make_song()
    song_id = repo.add(song, "letra original", [SongMoment.ENTRANCE])
    assert repo.get(song_id) == song
    assert repo.by_url(song.source_url or "") == (song_id, song)
    assert repo.by_url("https://nao/existe") is None

    changed = song.model_copy(update={"title": "Outro título", "artist": None})
    repo.update(song_id, changed, reviewed=True)
    assert repo.get(song_id) == changed
    assert [sid for sid, _ in repo.list_all()] == [song_id]

    repo.delete(song_id)
    assert repo.get(song_id) is None
    with pytest.raises(NotFoundError):
        repo.delete(song_id)


def test_unique_url(session: Session) -> None:
    repo = SongRepository(session)
    repo.add(make_song(), "a")
    with pytest.raises(DuplicateError):
        repo.add(make_song(title="Outro"), "b")
    # the session is usable after the failure; songs without URL may repeat
    repo.add(make_song(title="Sem url 1", url=None), "c")
    repo.add(make_song(title="Sem url 2", url=None), "d")
    assert len(repo.list_all()) == 3


def test_unique_alias(session: Session) -> None:
    repo = SongRepository(session)
    first = repo.add(make_song(), "a")
    second = repo.add(make_song(title="Outro", url=None), "b")
    repo.add_alias(first, "Me Chamaste")
    assert repo.aliases(first) == ["me chamaste"]
    with pytest.raises(DuplicateError):
        repo.add_alias(second, "me  CHAMASTE!")
    with pytest.raises(NotFoundError):
        repo.add_alias(999, "x")
    with pytest.raises(ValueError, match="vazio"):
        repo.add_alias(first, "  ")


def test_search_by_first_line_prefix(session: Session) -> None:
    repo = SongRepository(session)
    wanted = repo.add(
        make_song(title="Pescador de Homens", first_line="Me chamaste para caminhar…"), "x"
    )
    repo.add(make_song(title="Ave Maria", first_line="Ave Maria", url=None), "y")
    matches = repo.search("me chamaste")
    assert matches[0].song_id == wanted
    assert matches[0].score == 100
    assert matches[0].song.title == "Pescador de Homens"
    assert matches[0].song.stanzas[0].lines[0].text == "Me chamaste para caminhar…"


def test_search_ignores_accents_and_case(session: Session) -> None:
    repo = SongRepository(session)
    song_id = repo.add(make_song(title="Glória a Deus", first_line="Ó Senhor", url=None), "x")
    for term in ("GLORIA A DEUS", "glória a deus", "Gloria a Deus"):
        top = repo.search(term)[0]
        assert (top.song_id, top.score) == (song_id, 100)
    assert repo.search("o senhor")[0].song_id == song_id


def test_search_alias_fuzzy_and_limit(session: Session) -> None:
    repo = SongRepository(session)
    first = repo.add(
        make_song(title="Pescador de Homens", first_line="Tu te abeiraste", url=None), "x"
    )
    repo.add_alias(first, "barquinho")
    for i in range(6):
        repo.add(make_song(title=f"Canto de louvor {i}", first_line="Louvai", url=None), "z")
    assert repo.search("Barquinho")[0].score == 100
    typo = repo.search("pescadores de homem")
    assert typo[0].song_id == first and 60 <= typo[0].score < 100
    assert len(repo.search("canto de louvor", limit=3)) == 3
    assert repo.search("zzzzqqq") == []
    assert repo.search("   ") == []


def test_mass_roundtrip(session: Session) -> None:
    mass = Mass.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    repo = MassRepository(session)
    mass_id = repo.save(mass, MassFiles(pptx=Path("/tmp/a.pptx"), pdf=Path("/tmp/a.pdf")))

    session.expire_all()
    assert repo.get(mass_id) == mass
    [summary] = repo.list()
    assert summary.id == mass_id
    assert summary.date == mass.celebration.date
    assert summary.pptx_path == Path("/tmp/a.pptx")
    with pytest.raises(NotFoundError):
        repo.get(mass_id + 1)


def test_mass_links_known_songs_and_survives_song_delete(session: Session) -> None:
    mass = Mass.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    moment, song = next(iter(mass.songs.items()))
    songs = SongRepository(session)
    song_id = songs.add(song, "letra")
    mass_id = MassRepository(session).save(mass)
    linked = session.execute(
        text("SELECT song_id FROM mass_songs WHERE mass_id=:m AND moment=:mo"),
        {"m": mass_id, "mo": moment.value},
    ).scalar_one()
    assert linked == song_id
    songs.delete(song_id)  # ON DELETE SET NULL; the Mass snapshot is intact
    assert MassRepository(session).get(mass_id) == mass


def test_default_db_url(tmp_path: Path) -> None:
    paths = Paths(data=tmp_path / "d", config=tmp_path / "c.json", logs=tmp_path / "l")
    assert default_db_url(paths, env={}) == f"sqlite:///{tmp_path / 'd' / 'pallotti.db'}"
    assert default_db_url(paths, env={DB_URL_VAR: "sqlite:///x.db"}) == "sqlite:///x.db"
