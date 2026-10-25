"""Repertoire import from a Cifra Club songbook link (F4). Always a proposal, never applied."""

import json
import re
from collections.abc import Callable
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.text import normalize_search
from pallotti_slides.songs.downloaders import TIMEOUT_SECONDS, USER_AGENT, DownloadError

__all__ = ["ProposedSong", "RepertoireImporter", "RepertoireProposal", "propose_moments"]

CIFRA_CLUB = "https://www.cifraclub.com.br"

# Title hints, in priority order. ``None`` = fixed part of the Mass that has no song moment.
_HINTS: list[tuple[re.Pattern[str], SongMoment | None, str]] = [
    (
        re.compile(r"\bato penitencial\b|\bsenhor piedade\b"),
        SongMoment.PENITENTIAL_ACT,
        "Ato Penitencial",
    ),
    (re.compile(r"\baleluia\b|\baclamacao\b"), SongMoment.ACCLAMATION, "Aleluia/Aclamação"),
    (re.compile(r"\bcordeiro de deus\b|\bcordeiro\b"), None, "Cordeiro (parte fixa)"),
    (re.compile(r"^santo\b"), None, "Santo (parte fixa)"),
    (re.compile(r"\bgloria a deus\b|^gloria\b"), SongMoment.GLORIA, "Glória"),
]
# Moments filled by the order of the link when a title gives no hint.
_ORDER_MOMENTS = [
    SongMoment.ENTRANCE,
    SongMoment.OFFERTORY,
    SongMoment.COMMUNION,
    SongMoment.POST_COMMUNION,
    SongMoment.RECESSIONAL,
]


class ProposedSong(BaseModel):
    """One song of the link with the moment we suggest (``None`` = no suggestion)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    artist: str | None = None
    url: str
    moment: SongMoment | None = None
    confidence: Literal["high", "low", "none"] = "none"
    reason: str = ""


class RepertoireProposal(BaseModel):
    """What was found in the link. ``requires_confirmation`` is always true (SPEC F4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_url: str
    items: list[ProposedSong]
    unassigned: list[ProposedSong] = Field(default_factory=list)
    requires_confirmation: Literal[True] = True


def propose_moments(songs: list[tuple[str, str | None, str]]) -> RepertoireProposal:
    """Suggest a moment for each ``(title, artist, url)`` (link order is kept).

    Title hints first (high confidence); the rest take the free moments in the order of the
    Mass (low confidence). Mantra, Acclamation, Penitential Act and Gloria are never
    assigned by order alone.
    """
    hinted: list[tuple[SongMoment | None, str] | None] = []
    taken: set[SongMoment] = set()
    for title, _artist, _url in songs:
        key = normalize_search(title)
        found: tuple[SongMoment | None, str] | None = None
        for pattern, moment, label in _HINTS:
            if pattern.search(key) and (moment is None or moment not in taken):
                found = (moment, label)
                if moment is not None:
                    taken.add(moment)
                break
        hinted.append(found)
    free = [m for m in _ORDER_MOMENTS if m not in taken]
    items: list[ProposedSong] = []
    for (title, artist, url), hint in zip(songs, hinted, strict=True):
        if hint is not None and hint[0] is not None:
            items.append(
                ProposedSong(
                    title=title, artist=artist, url=url, moment=hint[0], confidence="high",
                    reason=f"o título indica {hint[1]}",
                )
            )  # fmt: skip
        elif hint is not None:
            items.append(
                ProposedSong(
                    title=title, artist=artist, url=url, reason=f"{hint[1]}: sem momento de canto"
                )
            )
        elif free:
            items.append(
                ProposedSong(
                    title=title, artist=artist, url=url, moment=free.pop(0), confidence="low",
                    reason="pela ordem do repertório",
                )
            )  # fmt: skip
        else:
            items.append(
                ProposedSong(title=title, artist=artist, url=url, reason="não sobrou momento")
            )
    return RepertoireProposal(
        source_url="", items=items, unassigned=[i for i in items if i.moment is None]
    )


def _songbook_items(html: str) -> list[dict[str, Any]]:
    """``items`` of the ``initialSongbook`` object embedded in the Next.js page data."""
    text = html.replace('\\"', '"')
    marker = '"initialSongbook":'
    start = text.find(marker)
    if start < 0:
        raise DownloadError("Não consegui ler o repertório desta página do Cifra Club.")
    try:
        book, _ = json.JSONDecoder().raw_decode(text, start + len(marker))
        items = book["items"]
    except (ValueError, KeyError, TypeError) as error:
        raise DownloadError("Não consegui ler o repertório desta página do Cifra Club.") from error
    return [item for item in items if isinstance(item, dict)]


class RepertoireImporter:
    """Reads a Cifra Club songbook and proposes a moment for each song."""

    def __init__(self, fetch: Callable[[str], str] | None = None) -> None:
        self._fetch = fetch or _http_get

    def load(self, url: str) -> RepertoireProposal:
        host = (urlparse(url).hostname or "").lower()
        if not (host == "cifraclub.com.br" or host.endswith(".cifraclub.com.br")):
            raise DownloadError("Só links de repertório do Cifra Club são suportados.")
        return self.parse(self._fetch(url), url)

    def parse(self, html: str, url: str) -> RepertoireProposal:
        """Proposal from the page HTML (``url`` is only recorded)."""
        songs: list[tuple[str, str | None, str]] = []
        for item in _songbook_items(html):
            try:
                version = item["version"]
                song_slug = version["song"]["slug"]
                title = version["song"]["name"]
                artist = version["artist"]
                songs.append(
                    (title, artist.get("name"), f"{CIFRA_CLUB}/{artist['slug']}/{song_slug}/")
                )
            except (KeyError, TypeError, AttributeError):
                continue
        if not songs:
            raise DownloadError("O repertório está vazio ou não pôde ser lido.")
        proposal = propose_moments(songs)
        return proposal.model_copy(update={"source_url": url})


def _http_get(url: str) -> str:
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
        )
    except httpx.HTTPError as error:
        raise DownloadError(
            "Não foi possível acessar o Cifra Club (sem conexão ou site fora do ar)."
        ) from error
    if response.status_code != 200:
        raise DownloadError(
            f"O Cifra Club recusou o acesso (erro {response.status_code}). "
            "Tente de novo mais tarde ou informe os cantos um a um."
        )
    return response.text
