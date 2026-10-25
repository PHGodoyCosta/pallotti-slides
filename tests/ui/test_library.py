from pathlib import Path
from typing import Any, cast

from pallotti_slides.application.library import SongLibrary
from pallotti_slides.db.repositories import SongRepository
from pallotti_slides.db.session import apply_migrations, make_engine, session_factory
from pallotti_slides.domain.enums import SongMoment, SongSource, StanzaType
from pallotti_slides.domain.models import Line, Song, Stanza
from pallotti_slides.songs.downloaders import RawLyrics
from pallotti_slides.songs.parser import ChorusDetector, LyricsParser
from pallotti_slides.songs.resolver import SongResolver
from pallotti_slides.songs.web_search import WebSongSearcher
from pallotti_slides.ui.pages.library import LibraryPage

URL = "https://www.letras.mus.br/a/b/"
LYRICS = "Ó Senhor\nVem nos salvar\n\nNós queremos\nTe louvar"


class _Downloader:
    def supports(self, url: str) -> bool:
        return True

    def download(self, url: str) -> RawLyrics:
        return RawLyrics(title="Da web", text=LYRICS, source=SongSource.LETRAS_MUS, url=url)


def _song(title: str, first: str = "Ó Senhor") -> Song:
    return Song(
        title=title,
        source=SongSource.MANUAL,
        stanzas=[Stanza(id=1, type=StanzaType.VERSE, lines=[Line(text=first)])],
        order=[1],
    )


def _page(qtbot, tmp_path: Path) -> tuple[LibraryPage, SongRepository]:  # type: ignore[no-untyped-def]
    engine = make_engine(f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    apply_migrations(engine)
    repo = SongRepository(session_factory(engine)())
    parser = LyricsParser(ChorusDetector())
    resolver = SongResolver(
        repo,
        [_Downloader()],
        parser,
        WebSongSearcher(cast(Any, object())),
    )
    page = LibraryPage(SongLibrary(repo, parser, resolver))
    qtbot.addWidget(page)
    page.show()
    return page, repo


def _titles(page: LibraryPage) -> list[str]:
    return [page.song_list.item(i).text() for i in range(page.song_list.count())]


def test_search_filter_and_empty_state(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    page, repo = _page(qtbot, tmp_path)
    assert page.empty_label.isVisible()
    repo.add(_song("Me Chamaste", "Ó Senhor"), "x", [SongMoment.ENTRANCE])
    repo.add(_song("Pão da Vida", "Eu sou o pão"), "x", [SongMoment.COMMUNION])
    page.refresh()
    assert _titles(page) == ["Me Chamaste", "Pão da Vida"]
    page.search_edit.setText("PAO")
    assert _titles(page) == ["Pão da Vida"]
    page.search_edit.setText("o senhor")
    assert _titles(page) == ["Me Chamaste"]  # first line, no accents
    page.search_edit.clear()
    page.moment_filter.setCurrentIndex(1 + list(SongMoment).index(SongMoment.COMMUNION))
    assert _titles(page) == ["Pão da Vida"]


def test_new_edit_save_and_delete_persist(qtbot, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    page, repo = _page(qtbot, tmp_path)
    monkeypatch.setattr(page, "ask_new_text", lambda: LYRICS)
    page.new_button.click()
    assert _titles(page) == ["Ó Senhor"]
    assert page.title_label.text() == "Ó Senhor"
    assert "Ainda não usado" in page.usage_label.text()

    edited = _song("Título editado", "Ó Senhor")
    monkeypatch.setattr(page, "edit_song", lambda _s: edited)
    page.edit_button.click()
    page.moment_boxes[SongMoment.OFFERTORY].setChecked(True)
    page.save_button.click()
    assert [s.title for _i, s in repo.list_all()] == ["Título editado"]
    assert page.moment_boxes[SongMoment.OFFERTORY].isChecked()

    page.alias_edit.setText("Meu apelido")
    page.add_alias_button.click()
    assert page.alias_list.count() == 1
    page.alias_list.setCurrentRow(0)
    page.remove_alias_button.click()
    assert page.alias_list.count() == 0

    monkeypatch.setattr(page, "confirm_delete", lambda _e: False)
    page.delete_button.click()
    assert repo.list_all()
    monkeypatch.setattr(page, "confirm_delete", lambda _e: True)
    page.delete_button.click()
    assert repo.list_all() == []
    assert _titles(page) == []


def test_new_from_url_runs_in_background(qtbot, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    page, repo = _page(qtbot, tmp_path)
    monkeypatch.setattr(page, "ask_new_text", lambda: URL)
    page.new_button.click()
    qtbot.waitUntil(lambda: page.song_list.count() == 1, timeout=5000)
    assert repo.by_url(URL) is not None


def test_merge_moves_aliases(qtbot, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    page, repo = _page(qtbot, tmp_path)
    keep = repo.add(_song("A Canto"), "x")
    dup = repo.add(_song("B Canto"), "x")
    repo.add_alias(dup, "apelido b")
    page.refresh(select_id=keep)
    choice: Any = lambda _keep, others: others[0].id  # noqa: E731
    monkeypatch.setattr(page, "ask_merge_target", choice)
    page.merge_button.click()
    assert _titles(page) == ["A Canto"]
    assert "apelido b" in [page.alias_list.item(i).text() for i in range(page.alias_list.count())]
    assert repo.get(dup) is None


def test_window_registers_library_page(window) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(window.library_page, LibraryPage)
