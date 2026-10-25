import datetime as dt
from pathlib import Path

import pytest
from songs.fakes import FakeDownloader, FakeLLM, raw

from pallotti_slides.application.library import SongLibrary
from pallotti_slides.db.repositories import MassRepository, NotFoundError, SongRepository
from pallotti_slides.db.session import apply_migrations, make_engine, session_factory
from pallotti_slides.domain.enums import (
    EucharisticPrayer,
    LiturgicalSeason,
    SongMoment,
    SongSource,
    StanzaType,
)
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Celebration, Line, Liturgy, Mass, Song, Stanza
from pallotti_slides.songs.parser import ChorusDetector, LyricsParser
from pallotti_slides.songs.resolver import SongResolver
from pallotti_slides.songs.web_search import WebSongSearcher

URL = "https://www.letras.mus.br/a/b/"
LYRICS = "Ó Senhor\nVem nos salvar\n\nNós queremos\nTe louvar"


def song(title: str, first: str = "Ó Senhor", url: str | None = None) -> Song:
    return Song(
        title=title,
        source=SongSource.MANUAL,
        source_url=url,
        stanzas=[Stanza(id=1, type=StanzaType.VERSE, lines=[Line(text=first)])],
        order=[1],
    )


def mass(date: dt.date, *songs: tuple[SongMoment, Song]) -> Mass:
    return Mass(
        celebration=Celebration(title="Domingo", date=date, season=LiturgicalSeason.ORDINARY_TIME),
        liturgy=Liturgy(
            first_reading="a",
            psalm_number="1",
            psalm_refrain="r",
            gospel="g",
            intercessions_response="i",
            eucharistic_prayer=EucharisticPrayer.III,
            mystery_of_faith="m",
        ),
        has_gloria=True,
        songs=dict(songs),
    )


@pytest.fixture
def parts(tmp_path: Path) -> tuple[SongLibrary, SongRepository, MassRepository]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    apply_migrations(engine)
    session = session_factory(engine)()
    repo = SongRepository(session)
    parser = LyricsParser(ChorusDetector())
    downloader = FakeDownloader({URL: raw("Canto da web", URL, LYRICS)})
    resolver = SongResolver(repo, [downloader], parser, WebSongSearcher(FakeLLM()))
    return SongLibrary(repo, parser, resolver), repo, MassRepository(session)


def test_create_from_lyrics_edit_and_delete_persist(parts) -> None:  # type: ignore[no-untyped-def]
    library, repo, _ = parts
    song_id, _ = library.create_from_lyrics(LYRICS, moments=[SongMoment.ENTRANCE])
    entry = library.get(song_id)
    assert entry.song.title == "Ó Senhor"
    assert entry.usual_moments == [SongMoment.ENTRANCE]
    assert repo.get(song_id) is not None

    edited = entry.song.model_copy(update={"title": "Novo título"})
    library.update(song_id, edited, [SongMoment.COMMUNION])
    again = library.get(song_id)
    assert again.song.title == "Novo título"
    assert again.usual_moments == [SongMoment.COMMUNION]
    assert again.reviewed

    library.delete(song_id)
    assert repo.get(song_id) is None
    with pytest.raises(NotFoundError):
        library.get(song_id)


def test_create_from_url_and_text_dispatch(parts) -> None:  # type: ignore[no-untyped-def]
    library, _repo, _ = parts
    song_id, _ = library.create(URL)
    assert library.get(song_id).song.source_url == URL
    again, _ = library.create(URL)  # already saved: same song
    assert again == song_id
    with pytest.raises(PallottiError):
        library.create("   ")


def test_search_by_title_alias_and_first_line_ignores_accents(parts) -> None:  # type: ignore[no-untyped-def]
    library, repo, _ = parts
    a = repo.add(song("Me Chamaste", first="Ó Senhor, vem"), "x", [SongMoment.ENTRANCE])
    b = repo.add(song("Pão da Vida", first="Eu sou o pão"), "x", [SongMoment.COMMUNION])
    library.add_alias(b, "Canção do Pão")

    def ids(term: str, moment: SongMoment | None = None) -> list[int]:
        return [e.id for e in library.search(term, moment)]

    assert ids("CHAMASTÉ".replace("É", "E")) == [a]
    assert ids("pao da vida") == [b]
    assert ids("cancao do pao") == [b]
    assert ids("zzz") == []
    assert ids("senhor") == [a]
    assert ids("") == [b, a] or ids("") == [a, b]
    assert ids("", SongMoment.COMMUNION) == [b]
    assert ids("senhor", SongMoment.COMMUNION) == []


def test_alias_management(parts) -> None:  # type: ignore[no-untyped-def]
    library, repo, _ = parts
    a = repo.add(song("A"), "x")
    library.add_alias(a, "Apelido Um")
    assert library.get(a).aliases == ["apelido um"]
    library.remove_alias(a, "Apelido Um")
    assert library.get(a).aliases == []


def test_usage_counts_and_last_date(parts) -> None:  # type: ignore[no-untyped-def]
    library, repo, masses = parts
    s = song("Canto")
    repo.add(s, "x")
    masses.save(mass(dt.date(2026, 10, 11), (SongMoment.ENTRANCE, s)))
    masses.save(mass(dt.date(2026, 10, 25), (SongMoment.RECESSIONAL, s)))
    (entry,) = library.list_entries()
    assert entry.uses == 2
    assert entry.last_used == dt.date(2026, 10, 25)
    assert entry.usage_text() == "Usado 2 vezes, última em 25/10/2026"


def test_merge_moves_aliases_history_and_moments(parts) -> None:  # type: ignore[no-untyped-def]
    library, repo, masses = parts
    keep_song, dup_song = song("Canto Certo"), song("Canto Duplicado")
    keep = repo.add(keep_song, "x", [SongMoment.ENTRANCE])
    dup = repo.add(dup_song, "x", [SongMoment.COMMUNION])
    library.add_alias(dup, "apelido do duplicado")
    masses.save(mass(dt.date(2026, 10, 25), (SongMoment.COMMUNION, dup_song)))

    library.merge(keep, dup)

    assert repo.get(dup) is None
    entry = library.get(keep)
    assert set(entry.aliases) == {"apelido do duplicado", "canto duplicado"}
    assert entry.uses == 1
    assert entry.last_used == dt.date(2026, 10, 25)
    assert entry.usual_moments == [SongMoment.ENTRANCE, SongMoment.COMMUNION]
    assert [e.id for e in library.search("apelido do duplicado")] == [keep]
    with pytest.raises(PallottiError):
        library.merge(keep, keep)
