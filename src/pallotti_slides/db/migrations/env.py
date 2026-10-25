"""Alembic environment: metadata from ``db/tables.py``, batch mode for SQLite."""

from alembic import context
from sqlalchemy import create_engine

from pallotti_slides.config import default_db_url
from pallotti_slides.db.tables import Base

config = context.config
target_metadata = Base.metadata


def _configure(**kwargs: object) -> None:
    context.configure(target_metadata=target_metadata, render_as_batch=True, **kwargs)  # type: ignore[arg-type]


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or default_db_url()
    _configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # apply_migrations() hands over its own connection
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return
    url = config.get_main_option("sqlalchemy.url") or default_db_url()
    engine = create_engine(url)
    with engine.connect() as conn:
        _configure(connection=conn)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
