import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pallotti_slides.application.container import Container
from pallotti_slides.application.mass_history import MassSummary
from pallotti_slides.application.settings_service import SettingsService
from pallotti_slides.config import Paths
from pallotti_slides.db.repositories import SongRepository
from pallotti_slides.db.session import apply_migrations, make_engine, session_factory
from pallotti_slides.domain.models import Mass
from pallotti_slides.songs.parser import ChorusDetector, LyricsParser
from pallotti_slides.ui.main_window import MainWindow


class FakeMassRepo:
    def __init__(self, summaries: list[MassSummary] | None = None) -> None:
        self.summaries = summaries or []
        self.masses: dict[int, Mass] = {}

    def list(self, limit: int = 50) -> list[MassSummary]:
        return self.summaries

    def get(self, mass_id: int) -> Mass:
        return self.masses[mass_id]


class FakeKeyring:
    """In-memory keyring; ``calls`` is not exposed to the UI."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get(self, service: str, user: str) -> str | None:
        return self.store.get((service, user))

    def set(self, service: str, user: str, value: str) -> None:
        self.store[(service, user)] = value

    def delete(self, service: str, user: str) -> None:
        del self.store[(service, user)]


def make_service(config: Path, keyring: FakeKeyring | None = None) -> SettingsService:
    kr = keyring or FakeKeyring()
    return SettingsService(
        config, env={}, keyring_get=kr.get, keyring_set=kr.set, keyring_delete=kr.delete
    )


class FakeContainer:
    """Stands in for ``Container``: no mass history, a throwaway config path."""

    closed = False

    def __init__(self) -> None:
        self.mass_repo = FakeMassRepo()
        self.paths = Paths(data=Path("."), config=Path("config.json"), logs=Path("."))
        engine = make_engine("sqlite://")
        apply_migrations(engine)
        self.song_repo = SongRepository(session_factory(engine)())
        self.parser = LyricsParser(ChorusDetector())
        self.resolver: Any = SimpleNamespace()

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def window(qtbot, tmp_path: Path) -> Iterator[MainWindow]:  # type: ignore[no-untyped-def]
    win = MainWindow(
        cast(Container, FakeContainer()), settings_service=make_service(tmp_path / "config.json")
    )
    qtbot.addWidget(win)
    win.show()
    yield win
