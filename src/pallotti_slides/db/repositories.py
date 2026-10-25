"""Repositories for songs and masses (ARQUITETURA §9).

Each mutating method commits its own transaction.
"""

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pallotti_slides.domain.enums import EucharisticPrayer, SongMoment
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Mass, Song, Stanza
from pallotti_slides.domain.text import normalize_search

from .tables import MassRow, MassSongRow, SongAliasRow, SongRow

EXACT_SCORE = 100.0
MIN_FUZZY_SCORE = 60.0


class DuplicateError(PallottiError, ValueError):
    """A unique value (song URL or alias) already exists."""


class NotFoundError(PallottiError, LookupError):
    """The requested row does not exist."""


@dataclass(frozen=True)
class Match:
    """A search result: ``song_id`` identifies the row (``Song`` has no id)."""

    song: Song
    score: float
    song_id: int


@dataclass(frozen=True)
class MassFiles:
    """Generated files of a saved Mass."""

    pptx: Path | None = None
    pdf: Path | None = None


@dataclass(frozen=True)
class MassSummary:
    """A line of the history list."""

    id: int
    date: dt.date
    title: str
    eucharistic_prayer: EucharisticPrayer
    pptx_path: Path | None
    pdf_path: Path | None
    created_at: dt.datetime


def _first_line(song: Song) -> str:
    stanzas: list[Stanza] = song.sequence() or song.stanzas
    for stanza in stanzas:
        if stanza.lines:
            return stanza.lines[0].text
    return ""


def _structure(song: Song) -> dict[str, object]:
    return {
        "stanzas": [stanza.model_dump(mode="json") for stanza in song.stanzas],
        "order": list(song.order),
    }


def _to_song(row: SongRow) -> Song:
    return Song.model_validate(
        {
            "title": row.title,
            "artist": row.artist,
            "source": row.source,
            "source_url": row.source_url,
            **row.structure,
        }
    )


class SongRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        song: Song,
        original_lyrics: str,
        usual_moments: Iterable[SongMoment] = (),
        reviewed: bool = False,
    ) -> int:
        """Insert a song and return its id. ``DuplicateError`` if the URL exists."""
        row = SongRow(
            title=song.title,
            title_search=normalize_search(song.title),
            first_line_search=normalize_search(_first_line(song)),
            artist=song.artist,
            source=song.source,
            source_url=song.source_url,
            original_lyrics=original_lyrics,
            structure=_structure(song),
            usual_moments=[moment.value for moment in usual_moments],
            reviewed=reviewed,
        )
        self._session.add(row)
        self._commit(f"Já existe um canto com a URL {song.source_url}.")
        return row.id

    def get(self, song_id: int) -> Song | None:
        row = self._session.get(SongRow, song_id)
        return _to_song(row) if row else None

    def by_url(self, url: str) -> tuple[int, Song] | None:
        row = self._session.scalar(select(SongRow).where(SongRow.source_url == url))
        return (row.id, _to_song(row)) if row else None

    def update(
        self,
        song_id: int,
        song: Song,
        reviewed: bool | None = None,
        usual_moments: Iterable[SongMoment] | None = None,
    ) -> None:
        row = self._row(song_id)
        row.title = song.title
        row.title_search = normalize_search(song.title)
        row.first_line_search = normalize_search(_first_line(song))
        row.artist = song.artist
        row.source = song.source
        row.source_url = song.source_url
        row.structure = _structure(song)
        if reviewed is not None:
            row.reviewed = reviewed
        if usual_moments is not None:
            row.usual_moments = [moment.value for moment in usual_moments]
        self._commit(f"Já existe um canto com a URL {song.source_url}.")

    def delete(self, song_id: int) -> None:
        self._session.delete(self._row(song_id))
        self._session.commit()

    def list_all(self) -> list[tuple[int, Song]]:
        rows = self._session.scalars(select(SongRow).order_by(SongRow.title_search)).all()
        return [(row.id, _to_song(row)) for row in rows]

    def add_alias(self, song_id: int, alias: str) -> None:
        """Add a search alias. ``DuplicateError`` if it already exists (any song)."""
        key = normalize_search(alias)
        if not key:
            raise ValueError("O apelido não pode ser vazio.")
        self._row(song_id)
        self._session.add(SongAliasRow(song_id=song_id, alias_search=key))
        self._commit(f"O apelido «{alias}» já está em uso.")

    def aliases(self, song_id: int) -> list[str]:
        return list(
            self._session.scalars(
                select(SongAliasRow.alias_search)
                .where(SongAliasRow.song_id == song_id)
                .order_by(SongAliasRow.id)
            )
        )

    def search(self, term: str, limit: int = 5) -> list[Match]:
        """Exact title/alias or first-line prefix = 100; otherwise rapidfuzz token_set_ratio."""
        key = normalize_search(term)
        if not key:
            return []
        # (song_id, candidate text, kind) for titles, aliases and first lines.
        candidates: list[tuple[int, str, str]] = []
        for song_id, title, first_line in self._session.execute(
            select(SongRow.id, SongRow.title_search, SongRow.first_line_search)
        ):
            candidates.append((song_id, title, "title"))
            candidates.append((song_id, first_line, "first_line"))
        for song_id, alias in self._session.execute(
            select(SongAliasRow.song_id, SongAliasRow.alias_search)
        ):
            candidates.append((song_id, alias, "alias"))

        best: dict[int, float] = {}
        for song_id, text, kind in candidates:
            if text == key or (kind == "first_line" and text.startswith(key)):
                best[song_id] = EXACT_SCORE
        fuzzy = process.extract(
            key,
            [text for _, text, _ in candidates],
            scorer=fuzz.token_set_ratio,
            score_cutoff=MIN_FUZZY_SCORE,
            limit=None,
        )
        for _text, score, index in fuzzy:
            song_id = candidates[index][0]
            best[song_id] = max(best.get(song_id, 0.0), float(score))

        ranked = sorted(best.items(), key=lambda item: -item[1])[:limit]
        matches: list[Match] = []
        for song_id, score in ranked:
            row = self._session.get(SongRow, song_id)
            if row is not None:
                matches.append(Match(song=_to_song(row), score=score, song_id=song_id))
        return matches

    def _row(self, song_id: int) -> SongRow:
        row = self._session.get(SongRow, song_id)
        if row is None:
            raise NotFoundError(f"Canto {song_id} não encontrado.")
        return row

    def _commit(self, duplicate_message: str) -> None:
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise DuplicateError(duplicate_message) from error


class MassRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, mass: Mass, files: MassFiles | None = None) -> int:
        """Store the Mass (JSON snapshot) and link its songs already in the library."""
        files = files or MassFiles()
        row = MassRow(
            date=mass.celebration.date,
            title=mass.celebration.title,
            season=mass.celebration.season,
            eucharistic_prayer=mass.liturgy.eucharistic_prayer,
            data=mass.model_dump(mode="json"),
            pptx_path=str(files.pptx) if files.pptx else None,
            pdf_path=str(files.pdf) if files.pdf else None,
        )
        for moment, song in mass.songs.items():
            row.songs.append(MassSongRow(moment=moment, song_id=self._find_song_id(song)))
        self._session.add(row)
        self._session.commit()
        return row.id

    def list(self, limit: int = 50) -> list[MassSummary]:
        rows = self._session.scalars(
            select(MassRow).order_by(MassRow.date.desc(), MassRow.id.desc()).limit(limit)
        )
        return [
            MassSummary(
                id=row.id,
                date=row.date,
                title=row.title,
                eucharistic_prayer=row.eucharistic_prayer,
                pptx_path=Path(row.pptx_path) if row.pptx_path else None,
                pdf_path=Path(row.pdf_path) if row.pdf_path else None,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def get(self, mass_id: int) -> Mass:
        row = self._session.get(MassRow, mass_id)
        if row is None:
            raise NotFoundError(f"Missa {mass_id} não encontrada.")
        return Mass.model_validate(row.data)

    def _find_song_id(self, song: Song) -> int | None:
        if song.source_url:
            found = self._session.scalar(
                select(SongRow.id).where(SongRow.source_url == song.source_url)
            )
            if found is not None:
                return found
        return self._session.scalar(
            select(SongRow.id)
            .where(SongRow.title_search == normalize_search(song.title))
            .order_by(SongRow.id)
            .limit(1)
        )
