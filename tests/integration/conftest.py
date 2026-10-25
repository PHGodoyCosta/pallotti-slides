import dataclasses
from pathlib import Path

import pytest

from pallotti_slides.config import Paths


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Never touch the user's real history database."""
    db = tmp_path_factory.mktemp("db") / "pallotti.db"
    monkeypatch.setenv("PALLOTTI_DB_URL", f"sqlite:///{db.as_posix()}")


@pytest.fixture(autouse=True)
def _isolated_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Never touch the user's real data folder (song deck cache, leaflet cache)."""
    data = tmp_path_factory.mktemp("data")
    real_default = Paths.default

    def default() -> Paths:
        return dataclasses.replace(real_default(), data=Path(data))

    monkeypatch.setattr(Paths, "default", staticmethod(default))
