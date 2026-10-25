import datetime as dt
from pathlib import Path

from songs.fakes import FakeDownloader, FakeLLM

from pallotti_slides.application.prepare_mass import MassPreparer, ResolverAdapter
from pallotti_slides.db.repositories import SongRepository
from pallotti_slides.db.session import apply_migrations, make_engine, session_factory
from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import SongRequest
from pallotti_slides.songs.interpreter import (
    InterpretedRequest,
    InterpretedRequests,
    RequestInterpreter,
)
from pallotti_slides.songs.parser import ChorusDetector, LyricsParser
from pallotti_slides.songs.resolver import SongResolver
from pallotti_slides.songs.web_search import WebSongSearcher

LYRICS = "Ó Senhor\nVem nos salvar\n\nNós queremos\nTe louvar"


class NoExtractor:
    def extract(self, pdf: Path) -> None:  # pragma: no cover
        raise AssertionError


def preparer(tmp_path: Path, llm: FakeLLM) -> MassPreparer:
    engine = make_engine(f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    apply_migrations(engine)
    repo = SongRepository(session_factory(engine)())
    resolver = SongResolver(
        repo, [FakeDownloader({})], LyricsParser(ChorusDetector()), WebSongSearcher(llm)
    )
    return MassPreparer(NoExtractor(), ResolverAdapter(resolver), RequestInterpreter(llm))  # type: ignore[arg-type]


def test_free_text_fills_only_empty_moments(tmp_path: Path) -> None:
    answer = InterpretedRequests(
        requests=[
            InterpretedRequest(moment=SongMoment.ENTRANCE, text="ignorado"),
            InterpretedRequest(moment=SongMoment.COMMUNION, text=LYRICS),
        ]
    )
    explicit = SongRequest(moment=SongMoment.ENTRANCE, text=LYRICS, kind="lyrics")
    draft = preparer(tmp_path, FakeLLM(answer)).prepare(
        dt.date(2026, 10, 25), None, [explicit], "Comunhão: ..."
    )
    assert set(draft.songs) == {SongMoment.ENTRANCE, SongMoment.COMMUNION}


def test_interpreter_failure_does_not_stop_explicit_requests(tmp_path: Path) -> None:
    explicit = SongRequest(moment=SongMoment.ENTRANCE, text=LYRICS, kind="lyrics")
    draft = preparer(tmp_path, FakeLLM(fail=True)).prepare(
        dt.date(2026, 10, 25), None, [explicit], "texto"
    )
    assert SongMoment.ENTRANCE in draft.songs
    assert any(n.field == "free_text" and n.level == "error" for n in draft.notices)


def test_unresolved_title_becomes_candidate_warning(tmp_path: Path) -> None:
    request = SongRequest(moment=SongMoment.ENTRANCE, text="inexistente", kind="title")
    draft = preparer(tmp_path, FakeLLM()).prepare(dt.date(2026, 10, 25), None, [request], None)
    assert draft.songs == {}
    assert draft.notices
