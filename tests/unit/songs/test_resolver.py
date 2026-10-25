from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pallotti_slides.db.repositories import SongRepository
from pallotti_slides.db.session import apply_migrations, make_engine, session_factory
from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import SongRequest
from pallotti_slides.llm.client import SearchResult
from pallotti_slides.songs.parser import ChorusDetector, LyricsParser
from pallotti_slides.songs.resolver import SongResolver
from pallotti_slides.songs.web_search import WebSongSearcher

from .fakes import FakeDownloader, FakeLLM, raw

URL = "https://www.letras.mus.br/padre-zezinho/me-chamaste/"
LYRICS = "Me chamaste para caminhar\nNa vida contigo\n\nTe seguirei\nSenhor"
PAGES = {URL: raw("Me chamaste", URL, LYRICS)}


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[SongRepository]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'r.db').as_posix()}")
    apply_migrations(engine)
    session: Session = session_factory(engine)()
    yield SongRepository(session)
    session.close()


def make(
    repo: SongRepository,
    downloader: FakeDownloader | None = None,
    llm: FakeLLM | None = None,
) -> tuple[SongResolver, FakeDownloader, FakeLLM]:
    downloader = downloader or FakeDownloader(PAGES)
    llm = llm or FakeLLM(results=[SearchResult(url=URL, title="Me chamaste - Padre Zezinho")])
    resolver = SongResolver(
        repo, [downloader], LyricsParser(ChorusDetector()), WebSongSearcher(llm)
    )
    return resolver, downloader, llm


def request(
    text: str, kind: str = "title", moment: SongMoment = SongMoment.ENTRANCE
) -> SongRequest:
    return SongRequest(moment=moment, text=text, kind=kind)  # type: ignore[arg-type]


def test_url_downloads_once_then_comes_from_the_library(repo: SongRepository) -> None:
    resolver, downloader, llm = make(repo)
    first = resolver.resolve(request(URL, "url"))
    assert first.song is not None and first.origin == "web"
    second = resolver.resolve(request(URL, "url"))
    assert second.song is not None and second.origin == "library"
    assert downloader.calls == [URL]
    assert llm.search_calls == []


def test_title_flow_web_then_confirm_then_offline(repo: SongRepository) -> None:
    resolver, downloader, llm = make(repo)
    first = resolver.resolve(request("me chamaste"))
    assert first.song is None and first.origin == "web"
    assert [c.url for c in first.candidates] == [URL]
    assert llm.search_calls[0]["domains"] == ["letras.mus.br", "cifraclub.com.br"]
    song = resolver.confirm(request("me chamaste"), first.candidates[0])
    assert song.title == "Me chamaste"
    assert "me chamaste" in repo.aliases(repo.by_url(URL)[0])  # type: ignore[index]

    calls = (len(downloader.calls), len(llm.search_calls))
    again = resolver.resolve(request("me chamaste"))
    assert again.song is not None and again.origin == "library"
    assert (len(downloader.calls), len(llm.search_calls)) == calls


def test_alias_finds_song_by_text_not_in_title(repo: SongRepository) -> None:
    resolver, downloader, _llm = make(repo)
    resolver.confirm(request("caminhar na vida"), resolver.resolve(request("x y z")).candidates[0])
    result = resolver.resolve(request("caminhar na vida", moment=SongMoment.COMMUNION))
    assert result.origin == "library" and result.song is not None
    assert len(downloader.calls) == 1


def test_first_line_fragment_matches_in_the_library(repo: SongRepository) -> None:
    resolver, _, llm = make(repo)
    resolver.resolve(request(URL, "url"))
    result = resolver.resolve(request("Me chamaste para caminhar na vida contigo"))
    assert result.song is not None and result.origin == "library"
    assert llm.search_calls == []


def test_middle_score_gives_library_candidates(repo: SongRepository) -> None:
    resolver, downloader, llm = make(repo)
    resolver.resolve(request(URL, "url"))
    result = resolver.resolve(request("me chamou caminhar"))
    assert result.song is None and result.origin == "library"
    assert result.candidates[0].song_id is not None
    assert llm.search_calls == []
    song = resolver.confirm(request("me chamou caminhar"), result.candidates[0])
    assert song.title == "Me chamaste"
    assert len(downloader.calls) == 1


def test_pasted_lyrics_are_saved_as_manual(repo: SongRepository) -> None:
    resolver, downloader, llm = make(repo)
    result = resolver.resolve(request(LYRICS, "lyrics"))
    assert result.song is not None and result.origin == "pasted"
    assert result.song.source.value == "manual"
    assert downloader.calls == [] and llm.search_calls == []
    assert len(repo.list_all()) == 1


def test_network_failure_is_a_notice_and_does_not_stop_others(repo: SongRepository) -> None:
    resolver, *_ = make(repo, FakeDownloader(PAGES, fail=True))
    failed = resolver.resolve(request(URL, "url"))
    assert failed.song is None
    assert failed.notices[0].level == "error" and failed.notices[0].field == "songs.entrance"
    ok = resolver.resolve(request(LYRICS, "lyrics", SongMoment.COMMUNION))
    assert ok.song is not None


def test_search_failure_is_a_notice(repo: SongRepository) -> None:
    resolver, *_ = make(repo, llm=FakeLLM(fail=True))
    result = resolver.resolve(request("qualquer"))
    assert result.song is None and result.notices[0].level == "error"


def test_unsupported_site_is_a_notice(repo: SongRepository) -> None:
    resolver, downloader, _ = make(repo)
    result = resolver.resolve(request("https://example.com/x/y/", "url"))
    assert result.song is None and "suportado" in result.notices[0].message
    assert downloader.calls == []


def test_web_candidates_only_from_allowed_domains(repo: SongRepository) -> None:
    llm = FakeLLM(
        results=[
            SearchResult(url="https://evil.example.com/a/b/", title="Ruim"),
            SearchResult(url="https://www.letras.mus.br.evil.com/a/b/", title="Ruim 2"),
            SearchResult(url="https://www.youtube.com/watch?v=1", title="Vídeo"),
            SearchResult(url="https://www.letras.mus.br/padre-zezinho/", title="Artista"),
            SearchResult(url="https://www.cifraclub.com.br/x/y/?k=1", title="Y - X - Cifra Club"),
            SearchResult(url="https://www.cifraclub.com.br/x/y/", title="dup"),
            *[
                SearchResult(
                    url=f"https://www.letras.mus.br/a/s{n}/", title=f"S{n} - A - LETRAS.MUS.BR"
                )
                for n in range(8)
            ],
        ]
    )
    found = WebSongSearcher(llm).search("y", "x")
    assert len(found) == 5
    assert all("evil" not in (c.url or "") and "youtube" not in (c.url or "") for c in found)
    assert found[0].url == "https://www.cifraclub.com.br/x/y/"
    assert (found[0].title, found[0].artist) == ("Y", "X")
    assert "x" in str(llm.search_calls[0]["query"])
