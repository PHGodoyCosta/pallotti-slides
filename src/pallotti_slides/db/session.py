"""Engine, session factory and migrations."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from pallotti_slides.config import default_db_url

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def make_engine(url: str | None = None) -> Engine:
    """Create the engine; ``None`` = ``PALLOTTI_DB_URL`` or ``Paths.data/pallotti.db``.

    For SQLite files the folder is created and foreign keys are enforced.
    """
    parsed = make_url(url or default_db_url())
    is_sqlite = parsed.get_backend_name() == "sqlite"
    if is_sqlite and parsed.database and parsed.database != ":memory:":
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(parsed)
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def apply_migrations(engine: Engine) -> None:
    """Run ``alembic upgrade head`` on ``engine``."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
