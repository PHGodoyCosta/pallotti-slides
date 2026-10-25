"""Web search for song pages restricted to the supported sites (F5 step 3)."""

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from pallotti_slides.llm.client import LLMClient

__all__ = ["ALLOWED_DOMAINS", "MAX_CANDIDATES", "SongCandidate", "WebSongSearcher"]

ALLOWED_DOMAINS = ["letras.mus.br", "cifraclub.com.br"]
MAX_CANDIDATES = 5
_SITE_SUFFIXES = ("letras.mus.br", "cifra club", "cifraclub")


class SongCandidate(BaseModel):
    """A song the user can pick. Web candidates have ``url``; library ones have ``song_id``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    artist: str | None = None
    url: str | None = None
    song_id: int | None = None


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in ("http", "https") and any(
        host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS
    )


def _is_song_page(url: str) -> bool:
    """``/artist/song/``: artist and album pages are not songs."""
    return len([part for part in urlparse(url).path.split("/") if part]) == 2


def _split_title(raw: str) -> tuple[str, str | None]:
    """ "Title - Artist - LETRAS.MUS.BR" -> (title, artist)."""
    parts = [part.strip() for part in raw.split(" - ")]
    if len(parts) > 1 and parts[-1].casefold().strip(". ") in _SITE_SUFFIXES:
        parts.pop()
    if len(parts) > 1:
        return " - ".join(parts[:-1]), parts[-1]
    return (parts[0] if parts else ""), None


class WebSongSearcher:
    """Asks the LLM's web search for song pages; the model returns URLs, never lyrics."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def search(self, title: str, artist: str | None = None) -> list[SongCandidate]:
        """Up to 5 candidates; any URL outside the allowed sites is discarded."""
        query = f"letra {title}" + (f" {artist}" if artist else "")
        results = self._llm.search_urls(
            query=query, domains=list(ALLOWED_DOMAINS), max_results=MAX_CANDIDATES * 2
        )
        candidates: list[SongCandidate] = []
        seen: set[str] = set()
        for result in results:
            if not _allowed(result.url) or not _is_song_page(result.url):
                continue
            parsed = urlparse(result.url)
            url = f"https://{parsed.hostname}{parsed.path.rstrip('/')}/"
            if url in seen:
                continue
            seen.add(url)
            found_title, found_artist = _split_title(result.title)
            candidates.append(
                SongCandidate(title=found_title or title, artist=found_artist, url=url)
            )
            if len(candidates) == MAX_CANDIDATES:
                break
        return candidates
