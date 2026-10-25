"""Song resolution: library first, then the internet (F5, ARQUITETURA §6)."""

import contextlib
from dataclasses import dataclass, field
from typing import Literal

from pallotti_slides.db.repositories import DuplicateError, SongRepository
from pallotti_slides.domain.enums import SongMoment, SongSource
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Notice, Song, SongRequest
from pallotti_slides.songs.downloaders import DownloadError, LyricsDownloader, RawLyrics
from pallotti_slides.songs.parser import LyricsParser
from pallotti_slides.songs.web_search import SongCandidate, WebSongSearcher

__all__ = ["ResolutionResult", "SongResolver"]

STRONG_SCORE = 90.0
CANDIDATE_SCORE = 70.0


@dataclass(frozen=True)
class ResolutionResult:
    """``song`` is set when resolved; otherwise ``candidates`` wait for the user's choice."""

    song: Song | None
    origin: Literal["library", "web", "pasted", "none"]
    candidates: list[SongCandidate] = field(default_factory=list)
    notices: list[Notice] = field(default_factory=list)


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return " ".join(line.split())[:120]
    return "Canto"


class SongResolver:
    """Resolves ``SongRequest`` into a ``Song``: URL/title in the library, then the web."""

    def __init__(
        self,
        repo: SongRepository,
        downloaders: list[LyricsDownloader],
        parser: LyricsParser,
        searcher: WebSongSearcher,
    ) -> None:
        self._repo = repo
        self._downloaders = downloaders
        self._parser = parser
        self._searcher = searcher

    def resolve(self, request: SongRequest) -> ResolutionResult:
        """Never raises for recoverable problems: they come back as notices."""
        where = f"songs.{request.moment.value}"
        try:
            if request.kind == "lyrics":
                return self._from_lyrics(request, where)
            if request.kind == "url":
                return self._from_url(request.text.strip(), request.moment, where)
            return self._from_title(request, where)
        except PallottiError as error:
            return ResolutionResult(
                song=None,
                origin="none",
                notices=[Notice(level="error", message=str(error), field=where)],
            )

    def import_url(self, url: str) -> ResolutionResult:
        """Resolve a URL with no moment (library import)."""
        try:
            return self._from_url(url.strip(), None, "songs")
        except PallottiError as error:
            return ResolutionResult(
                song=None,
                origin="none",
                notices=[Notice(level="error", message=str(error), field="songs")],
            )

    def confirm(self, request: SongRequest, candidate: SongCandidate) -> Song:
        """Use the chosen candidate (library or download+save) and alias the request text."""
        song_id: int
        song: Song | None
        if candidate.song_id is not None:
            song_id, song = candidate.song_id, self._repo.get(candidate.song_id)
            if song is None:
                raise PallottiError("O canto escolhido não está mais na biblioteca.")
        elif candidate.url:
            song_id, song, _ = self._fetch_and_save(candidate.url, request.moment)
        else:
            raise PallottiError("O candidato não tem endereço nem registro na biblioteca.")
        if request.kind != "lyrics":
            self._alias(song_id, request.text)
        return song

    def _from_lyrics(self, request: SongRequest, where: str) -> ResolutionResult:
        raw = RawLyrics(
            title=_first_line(request.text), text=request.text, source=SongSource.MANUAL
        )
        song, notices = self._parser.parse(raw)
        self._repo.add(song, request.text, usual_moments=[request.moment])
        return ResolutionResult(song=song, origin="pasted", notices=_scoped(notices, where))

    def _from_url(self, url: str, moment: SongMoment | None, where: str) -> ResolutionResult:
        hit = self._repo.by_url(url)
        if hit is None:
            exact = [m for m in self._repo.search(url, limit=1) if m.score >= 100.0]
            if exact:  # the URL was asked before and saved as an alias
                return ResolutionResult(song=exact[0].song, origin="library")
        else:
            return ResolutionResult(song=hit[1], origin="library")
        song_id, song, notices = self._fetch_and_save(url, moment)
        self._alias(song_id, url)
        return ResolutionResult(song=song, origin="web", notices=_scoped(notices, where))

    def _from_title(self, request: SongRequest, where: str) -> ResolutionResult:
        matches = [m for m in self._repo.search(request.text) if m.score >= CANDIDATE_SCORE]
        if matches and matches[0].score >= STRONG_SCORE:
            best = matches[0]
            self._alias(best.song_id, request.text)
            return ResolutionResult(song=best.song, origin="library")
        if matches:
            candidates = [
                SongCandidate(
                    title=m.song.title,
                    artist=m.song.artist,
                    url=m.song.source_url,
                    song_id=m.song_id,
                )
                for m in matches
            ]
            return ResolutionResult(song=None, origin="library", candidates=candidates)
        found = self._searcher.search(request.text)
        if not found:
            return ResolutionResult(
                song=None,
                origin="none",
                notices=[
                    Notice(
                        level="warning",
                        message=f"Não encontrei «{request.text}». Informe o link ou cole a letra.",
                        field=where,
                    )
                ],
            )
        return ResolutionResult(song=None, origin="web", candidates=found)

    def _fetch_and_save(
        self, url: str, moment: SongMoment | None
    ) -> tuple[int, Song, list[Notice]]:
        existing = self._repo.by_url(url)
        if existing is not None:
            return existing[0], existing[1], []
        downloader = next((d for d in self._downloaders if d.supports(url)), None)
        if downloader is None:
            raise DownloadError(
                "Este site não é suportado. Use Letras.mus.br ou Cifra Club, ou cole a letra."
            )
        raw = downloader.download(url)
        # Cifra Club may hand back the Letras.mus.br page: it can already be saved.
        if raw.url and raw.url != url:
            existing = self._repo.by_url(raw.url)
            if existing is not None:
                return existing[0], existing[1], []
        song, notices = self._parser.parse(raw)
        usual = [moment] if moment is not None else []
        song_id = self._repo.add(song, raw.text, usual_moments=usual)
        return song_id, song, notices

    def _alias(self, song_id: int, text: str) -> None:
        # Already in use (same or another song) or empty: keep what exists.
        with contextlib.suppress(DuplicateError, ValueError):
            self._repo.add_alias(song_id, text)


def _scoped(notices: list[Notice], where: str) -> list[Notice]:
    return [n.model_copy(update={"field": n.field or where}) for n in notices]
