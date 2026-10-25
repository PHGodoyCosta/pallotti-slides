"""Raw lyrics, the downloader contract and the Letras.mus.br / Cifra Club downloaders (§6).

Selectors were confirmed against the saved HTML in ``tests/fixtures/html/``:
- Letras.mus.br: title ``div.head.--lyric h1``, artist ``div.head.--lyric h2``, lyrics
  ``div.lyric-original`` (stanzas in ``<p>``, lines separated by ``<br>``).
- Cifra Club: title ``h1`` (inside ``div[data-chord-select]``), artist the ``h2`` next to it,
  chord sheet ``pre[data-chord-content]`` (CSS class names are hashed, so they are not used).
"""

import re
from typing import Protocol
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, ConfigDict

from pallotti_slides.domain.enums import SongSource
from pallotti_slides.domain.text import normalize_search
from pallotti_slides.songs.fetcher import DownloadError, PageFetcher, default_fetcher

__all__ = [
    "CifraClubDownloader",
    "DownloadError",
    "LetrasMusDownloader",
    "LyricsDownloader",
    "RawLyrics",
    "clean_prolongations",
    "strip_chords",
]


class RawLyrics(BaseModel):
    """Lyrics as obtained from a site or pasted by the user, before structuring."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    artist: str | None = None
    text: str
    source: SongSource
    url: str | None = None


class LyricsDownloader(Protocol):
    """Fetches the lyrics of one URL."""

    def supports(self, url: str) -> bool: ...

    def download(self, url: str) -> RawLyrics: ...


_CHORD = r"[A-G][#b]?(?:maj|min|dim|aug|sus|add|m|M)?[º°ø]?\d*(?:\([^)\s]*\))?(?:/[A-G][#b]?)?"
_CHORD_TOKEN = re.compile(rf"{_CHORD}\.?")
_FILLER_TOKEN = re.compile(r"[|()\-x/.:]+|\(?\d+x\)?|x\d+", re.IGNORECASE)
_LABEL = re.compile(
    r"^\s*\[?\s*(?:intro(?:du[cç][aã]o)?|solo|ponte|final|interl[uú]dio|riff|base|refr[aã]o)"
    r"[^\]:]*\]?\s*:?\s*",
    re.IGNORECASE,
)
_TAB_LINE = re.compile(r"^\s*[EADGBe]?\s*\|[-\dhpbrx/\\~^()|\s.]*$")
_BRACKET_CHORD = re.compile(rf"\[\s*{_CHORD}\s*\]")
_BLANK_RUN = re.compile(r"\n{3,}")


_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))
_SECTION_LABEL = re.compile(r"^\s*\[[^\]]*\]\s*$")
_CHORUS_LABEL = re.compile(r"^\s*\[\s*refr[aã]o[^\]]*\]\s*$", re.IGNORECASE)
_PART_OF = re.compile(r"^\s*parte\s+\d+\s+de\s+\d+\s*$", re.IGNORECASE)
_LETTER = r"[^\W\d_]"
_PROLONGATION = re.compile(rf"({_LETTER})[._]{{2,}}({_LETTER})")
_VOWELS = "aeiouáéíóúâêôãõàü"


def _join_prolongation(match: re.Match[str]) -> str:
    left, right = match.group(1), match.group(2)
    if left.lower() == right.lower() and left.lower() in _VOWELS:
        return left  # "perdoa....ai" -> "perdoai": the sung vowel is not repeated
    return left + right


def clean_prolongations(text: str) -> str:
    """Remove prolongation marks: "liberta..dos" -> "libertados", "Mari____a" -> "Maria"."""
    return _PROLONGATION.sub(_join_prolongation, text)


def _is_chord_line(line: str) -> bool:
    """True when the line holds only chords (and bar/repeat marks), and at least one chord."""
    tokens = line.split()
    if not tokens:
        return False
    chords = 0
    for token in tokens:
        if _CHORD_TOKEN.fullmatch(token):
            chords += 1
        elif not _FILLER_TOKEN.fullmatch(token):
            return False
    return chords > 0


def strip_chords(text: str) -> str:
    """Remove chords, section labels and tablature from the ``<pre>`` text of a chord sheet.

    Drops invisible characters, chord-only lines (also after labels such as "Intro:"),
    tablature, ``[Intro]``-style section labels, "Parte 1 de 2" and bracketed chords inside
    lyric lines ("Te [Am]amarei" -> "Te amarei"). ``[Refrão]`` labels are kept: the parser
    uses them. Syllable prolongations are cleaned.
    """
    text = text.translate(_INVISIBLE).replace("\xa0", " ")
    kept: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _TAB_LINE.match(raw) or _PART_OF.match(raw):
            continue
        if _SECTION_LABEL.match(raw) and not _CHORUS_LABEL.match(raw):
            continue
        if raw.strip() and not any(c.isalnum() for c in raw):
            continue  # leftovers such as "( )" or "." where chords used to be
        label = _LABEL.match(raw)
        rest = raw[label.end() :] if label else raw
        if _is_chord_line(rest):
            continue
        line = _BRACKET_CHORD.sub("", raw)
        if line != raw:
            line = re.sub(r"[ \t]{2,}", " ", line).rstrip()
            if not line.strip():
                continue
        kept.append(line.rstrip())
    cleaned = _BLANK_RUN.sub("\n\n", "\n".join(kept)).strip("\n")
    return clean_prolongations(cleaned)


def _squash(text: str) -> str:
    return " ".join(text.split())


def _path_parts(url: str) -> tuple[str, str] | None:
    """``(artist, song)`` slugs of a ``/artist/song/`` URL, or None."""
    parts = [part for part in urlparse(url).path.split("/") if part]
    return (parts[0], parts[1]) if len(parts) == 2 else None


def _same_title(letras_title: str, other: str) -> bool:
    """Titles match ignoring case, accents and punctuation (``other`` may be a URL slug)."""
    return _title_key(letras_title) == _title_key(other)


def _title_key(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", normalize_search(text)).split())


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


class LetrasMusDownloader:
    """Downloads lyrics from letras.mus.br."""

    SITE = "Letras.mus.br"

    def __init__(self, fetcher: PageFetcher | None = None) -> None:
        self._fetcher = fetcher or default_fetcher()

    def supports(self, url: str) -> bool:
        host = _host(url)
        return host == "letras.mus.br" or host.endswith(".letras.mus.br")

    def download(self, url: str) -> RawLyrics:
        return self.parse(BeautifulSoup(self._fetcher.get(url, self.SITE), "html.parser"), url)

    @staticmethod
    def parse(soup: BeautifulSoup, url: str) -> RawLyrics:
        """Extract title, artist and lyrics from an already parsed Letras.mus.br page."""
        head = soup.select_one("div.head.--lyric")
        lyric = soup.select_one("div.lyric-original")
        title_tag = head.select_one("h1") if head else None
        if lyric is None or title_tag is None:
            raise DownloadError(f"Não encontrei a letra na página do {LetrasMusDownloader.SITE}.")
        artist_tag = head.select_one("h2") if head else None
        stanzas: list[str] = []
        for paragraph in lyric.select("p"):
            for br in paragraph.select("br"):
                br.replace_with("\n")
            lines = [_squash(line) for line in paragraph.get_text().split("\n")]
            block = "\n".join(line for line in lines if line)
            if block:
                stanzas.append(block)
        text = clean_prolongations("\n\n".join(stanzas))
        if not text:
            raise DownloadError(f"A letra da página do {LetrasMusDownloader.SITE} está vazia.")
        return RawLyrics(
            title=_squash(title_tag.get_text(" ")),
            artist=_squash(artist_tag.get_text(" ")) if artist_tag else None,
            text=text,
            source=SongSource.LETRAS_MUS,
            url=url,
        )


class CifraClubDownloader:
    """Downloads lyrics from cifraclub.com.br.

    Order: the same ``artist/song`` on Letras.mus.br first (same company), accepted only when its
    title matches (``normalize_search``), because the same slug is sometimes another song; then
    the Cifra Club page (``httpx``, and ``curl_cffi`` when blocked), without chords. If the site
    cannot be reached, ``DownloadError`` asks the user to paste the lyrics.
    """

    SITE = "Cifra Club"
    _GENERIC_ARTISTS = frozenset({"catolicas"})

    def __init__(
        self, fetcher: PageFetcher | None = None, letras: LetrasMusDownloader | None = None
    ) -> None:
        self._fetcher = fetcher or default_fetcher()
        self._letras = letras or LetrasMusDownloader(self._fetcher)

    def supports(self, url: str) -> bool:
        host = _host(url)
        return host == "cifraclub.com.br" or host.endswith(".cifraclub.com.br")

    def download(self, url: str) -> RawLyrics:
        letras = self._letras_equivalent(url)
        slugs = _path_parts(url)
        if letras is not None and slugs is not None and _same_title(letras.title, slugs[1]):
            return letras  # the slug already confirms the title: no Cifra Club request
        cifra = self.parse(BeautifulSoup(self._fetcher.get(url, self.SITE), "html.parser"), url)
        if letras is not None and _same_title(letras.title, cifra.title):
            return letras
        return cifra

    def _letras_equivalent(self, url: str) -> RawLyrics | None:
        slugs = _path_parts(url)
        if slugs is None:
            return None
        try:
            return self._letras.download(f"https://www.letras.mus.br/{slugs[0]}/{slugs[1]}/")
        except DownloadError:
            return None

    @classmethod
    def parse(cls, soup: BeautifulSoup, url: str) -> RawLyrics:
        """Extract title, artist and chord-free lyrics from an already parsed Cifra Club page."""
        pre = soup.select_one("pre[data-chord-content]") or soup.select_one("pre")
        title_tag = soup.select_one("h1")
        if pre is None or title_tag is None:
            raise DownloadError(f"Não encontrei a cifra na página do {cls.SITE}.")
        text = strip_chords(pre.get_text())
        if not text:
            raise DownloadError(f"A letra da página do {cls.SITE} está vazia.")
        slugs = _path_parts(url)
        artist_tag = title_tag.find_next("h2")
        artist = None
        if isinstance(artist_tag, Tag) and not (slugs and slugs[0] in cls._GENERIC_ARTISTS):
            artist = _squash(artist_tag.get_text(" ")) or None
        return RawLyrics(
            title=_squash(title_tag.get_text(" ")),
            artist=artist,
            text=text,
            source=SongSource.CIFRA_CLUB,
            url=url,
        )
