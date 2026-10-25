"""SQLAlchemy tables (ARQUITETURA §9). Portable types: JSON and text enums."""

import datetime as dt
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pallotti_slides.domain.enums import (
    EucharisticPrayer,
    LiturgicalSeason,
    SongMoment,
    SongSource,
)


def utc_now() -> dt.datetime:
    """Naive UTC timestamp (SQLite does not keep time zones)."""
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def _enum(cls: type[StrEnum], length: int) -> Enum:
    """Enum stored as text with the enum *values* (not names), no native type."""
    return Enum(
        cls,
        native_enum=False,
        length=length,
        create_constraint=False,
        values_callable=lambda e: [member.value for member in e],
    )


class Base(DeclarativeBase):
    pass


class SongRow(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    title_search: Mapped[str] = mapped_column(String(200), index=True)
    first_line_search: Mapped[str] = mapped_column(String(300), index=True)
    artist: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[SongSource] = mapped_column(_enum(SongSource, 20))
    source_url: Mapped[str | None] = mapped_column(String(500), unique=True)
    original_lyrics: Mapped[str] = mapped_column(Text)
    structure: Mapped[dict[str, Any]] = mapped_column(JSON)
    usual_moments: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    aliases: Mapped[list["SongAliasRow"]] = relationship(
        back_populates="song", cascade="all, delete-orphan", passive_deletes=True
    )


class SongAliasRow(Base):
    __tablename__ = "song_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"))
    alias_search: Mapped[str] = mapped_column(String(200), unique=True)

    song: Mapped[SongRow] = relationship(back_populates="aliases")


class MassRow(Base):
    __tablename__ = "masses"
    __table_args__ = (Index("ix_masses_date", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(200))
    season: Mapped[LiturgicalSeason] = mapped_column(_enum(LiturgicalSeason, 20))
    eucharistic_prayer: Mapped[EucharisticPrayer] = mapped_column(_enum(EucharisticPrayer, 10))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    pptx_path: Mapped[str | None] = mapped_column(String(500))
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utc_now)

    songs: Mapped[list["MassSongRow"]] = relationship(
        back_populates="mass", cascade="all, delete-orphan", passive_deletes=True
    )


class MassSongRow(Base):
    __tablename__ = "mass_songs"

    mass_id: Mapped[int] = mapped_column(
        ForeignKey("masses.id", ondelete="CASCADE"), primary_key=True
    )
    moment: Mapped[SongMoment] = mapped_column(_enum(SongMoment, 20), primary_key=True)
    song_id: Mapped[int | None] = mapped_column(ForeignKey("songs.id", ondelete="SET NULL"))

    mass: Mapped[MassRow] = relationship(back_populates="songs")
