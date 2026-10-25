"""Song library use cases: list, search, create, edit, aliases, merge and delete (SPEC F12).

Built on top of the public API of ``SongRepository`` (no ORM rows or sessions here).
"""

import datetime as dt
import threading
from dataclasses import dataclass, field
from typing import Protocol

from pallotti_slides.application.container import Container
from pallotti_slides.db.repositories import SongRecord, SongRepository, SongUsage
from pallotti_slides.domain.enums import SongMoment, SongSource
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Notice, Song
from pallotti_slides.domain.text import looks_like_url, normalize_search
from pallotti_slides.songs.downloaders import RawLyrics
from pallotti_slides.songs.resolver import ResolutionResult

__all__ = ["LibraryEntry", "LyricsStructurer", "SongImporter", "SongLibrary"]


class LyricsStructurer(Protocol):
    def parse(self, raw: RawLyrics) -> tuple[Song, list[Notice]]: ...


class SongImporter(Protocol):
    def import_url(self, url: str) -> ResolutionResult: ...


@dataclass(frozen=True)
class LibraryEntry:
    """A song of the library with its metadata and usage."""

    id: int
    song: Song
    aliases: list[str] = field(default_factory=list)
    usual_moments: list[SongMoment] = field(default_factory=list)
    reviewed: bool = False
    uses: int = 0
    last_used: dt.date | None = None

    @property
    def first_line(self) -> str:
        for stanza in self.song.sequence() or self.song.stanzas:
            if stanza.lines:
                return stanza.lines[0].text
        return ""

    def usage_text(self) -> str:
        """\"Usado 3 vezes, última em 25/10/2026\" (Portuguese, for the interface)."""
        if not self.uses or self.last_used is None:
            return "Ainda não usado em nenhuma missa"
        times = "1 vez" if self.uses == 1 else f"{self.uses} vezes"
        return f"Usado {times}, última em {self.last_used.strftime('%d/%m/%Y')}"


class _Lazy:
    """Looks ``parser``/``resolver`` up in the container only when they are used."""

    def __init__(self, container: Container) -> None:
        self._container = container

    def parse(self, raw: RawLyrics) -> tuple[Song, list[Notice]]:
        return self._container.parser.parse(raw)

    def import_url(self, url: str) -> ResolutionResult:
        return self._container.resolver.import_url(url)


class SongLibrary:
    """Operations of the Biblioteca page. Thread-safe (the page imports URLs in a worker)."""

    def __init__(
        self,
        repo: SongRepository,
        parser: LyricsStructurer,
        resolver: SongImporter,
    ) -> None:
        self._repo = repo
        self._parser = parser
        self._resolver = resolver
        self._lock = threading.RLock()

    @classmethod
    def from_container(cls, container: Container) -> "SongLibrary":
        lazy = _Lazy(container)
        return cls(container.song_repo, lazy, lazy)

    # -- reading -------------------------------------------------------------------------

    def list_entries(self, term: str = "", moment: SongMoment | None = None) -> list[LibraryEntry]:
        """Songs ordered by title; ``term`` matches title, alias or first line (no accents)."""
        key = normalize_search(term)
        with self._lock:
            usage = self._repo.usage_all()
            entries: list[LibraryEntry] = []
            for record in self._repo.records():
                texts = (record.title_search, record.first_line_search, *record.aliases)
                if key and not any(key in text for text in texts):
                    continue
                if moment is not None and moment not in record.usual_moments:
                    continue
                entries.append(_entry(record, usage.get(record.id, SongUsage())))
            return entries

    def search(self, term: str, moment: SongMoment | None = None) -> list[LibraryEntry]:
        return self.list_entries(term, moment)

    def get(self, song_id: int) -> LibraryEntry:
        with self._lock:
            return _entry(self._repo.record(song_id), self._repo.usage(song_id))

    # -- creating ------------------------------------------------------------------------

    def create_from_lyrics(
        self, text: str, title: str | None = None, moments: list[SongMoment] | None = None
    ) -> tuple[int, list[Notice]]:
        """Structure pasted lyrics (parser) and save them. Title defaults to the first line."""
        body = text.strip()
        if not body:
            raise PallottiError("Cole a letra do canto (ou um endereço).")
        first = next(line.strip() for line in body.splitlines() if line.strip())
        raw = RawLyrics(title=(title or first)[:120], text=body, source=SongSource.MANUAL)
        with self._lock:
            song, notices = self._parser.parse(raw)
            return self._repo.add(song, body, usual_moments=moments or []), notices

    def create_from_url(self, url: str) -> tuple[int, list[Notice]]:
        """Download, structure and save the song of ``url`` (or reuse the one already saved)."""
        with self._lock:
            result = self._resolver.import_url(url.strip())
            if result.song is None:
                detail = "; ".join(n.message for n in result.notices) or "Falha desconhecida."
                raise PallottiError(f"Não foi possível importar o canto: {detail}")
            hit = self._repo.by_url(result.song.source_url) if result.song.source_url else None
            if hit is not None:
                return hit[0], list(result.notices)
            exact = [m for m in self._repo.search(result.song.title, limit=3) if m.score >= 100.0]
            if not exact:
                raise PallottiError("O canto importado não foi encontrado na biblioteca.")
            return exact[0].song_id, list(result.notices)

    def create(self, text: str) -> tuple[int, list[Notice]]:
        """Pasted lyrics, or an address (``looks_like_url``)."""
        if looks_like_url(text):
            return self.create_from_url(text)
        return self.create_from_lyrics(text)

    # -- editing -------------------------------------------------------------------------

    def update(
        self,
        song_id: int,
        song: Song,
        usual_moments: list[SongMoment] | None = None,
    ) -> None:
        """Save the edited structure (marks the song as reviewed)."""
        with self._lock:
            self._repo.update(song_id, song, reviewed=True, usual_moments=usual_moments)

    def add_alias(self, song_id: int, alias: str) -> None:
        with self._lock:
            self._repo.add_alias(song_id, alias)

    def remove_alias(self, song_id: int, alias: str) -> None:
        with self._lock:
            self._repo.remove_alias(song_id, alias)

    # -- merge and delete ----------------------------------------------------------------

    def merge(self, keep_id: int, duplicate_id: int) -> None:
        """Move aliases, the duplicate's title and history to ``keep_id`` and delete the other."""
        if keep_id == duplicate_id:
            raise PallottiError("Escolha dois cantos diferentes para mesclar.")
        if keep_id == duplicate_id:
            raise PallottiError("Escolha dois cantos diferentes para mesclar.")
        with self._lock:
            self._repo.merge(keep_id, duplicate_id)

    def delete(self, song_id: int) -> None:
        with self._lock:
            self._repo.delete(song_id)


def _entry(record: SongRecord, usage: SongUsage) -> LibraryEntry:
    return LibraryEntry(
        id=record.id,
        song=record.song,
        aliases=record.aliases,
        usual_moments=record.usual_moments,
        reviewed=record.reviewed,
        uses=usage.count,
        last_used=usage.last_date,
    )
