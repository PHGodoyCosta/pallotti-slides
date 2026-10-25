import pytest


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Never touch the user's real history database."""
    db = tmp_path_factory.mktemp("db") / "pallotti.db"
    monkeypatch.setenv("PALLOTTI_DB_URL", f"sqlite:///{db.as_posix()}")
