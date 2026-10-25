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

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, ConfigDict

from pallotti_slides.domain.enums import SongSource
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.text import normalize_search

USER_AGENT = "PallottiSlides/0.1 (gerador de slides paroquial; +https://github.com/PHGodoyCosta)"
TIMEOUT_SECONDS = 15.0


class DownloadError(PallottiError):
    """The lyrics page could not be downloaded or understood; the message is for the user."""


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


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


class _PageFetcher:
    """HTTP GET with identified User-Agent and 15 s timeout; errors become ``DownloadError``."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(follow_redirects=True)

    def get(self, url: str, site: str) -> BeautifulSoup:
        try:
            response = self._client.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as error:
            raise DownloadError(
                f"Não foi possível acessar o {site} (sem conexão ou site fora do ar). "
                "Verifique a internet ou cole a letra."
            ) from error
        if response.status_code == 404:
            raise DownloadError(f"A página não foi encontrada no {site}: {url}")
        if response.status_code != 200:
            raise DownloadError(
                f"O {site} recusou o acesso (erro {response.status_code}). "
                "Tente de novo mais tarde ou cole a letra."
            )
        return BeautifulSoup(response.text, "html.parser")


class LetrasMusDownloader:
    """Downloads lyrics from letras.mus.br."""

    SITE = "Letras.mus.br"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._fetcher = _PageFetcher(client)

    def supports(self, url: str) -> bool:
        host = _host(url)
        return host == "letras.mus.br" or host.endswith(".letras.mus.br")

    def download(self, url: str) -> RawLyrics:
        return self.parse(self._fetcher.get(url, self.SITE), url)

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

    Tries the same ``artist/song`` on Letras.mus.br first (same company); it is only used when
    its title matches the Cifra Club one (``normalize_search``), because the same slug is
    sometimes another song. Otherwise the chord sheet is used, without chords.
    """

    SITE = "Cifra Club"
    _GENERIC_ARTISTS = frozenset({"catolicas"})

    def __init__(
        self, client: httpx.Client | None = None, letras: LetrasMusDownloader | None = None
    ) -> None:
        self._fetcher = _PageFetcher(client)
        self._letras = letras or LetrasMusDownloader(client)

    def supports(self, url: str) -> bool:
        host = _host(url)
        return host == "cifraclub.com.br" or host.endswith(".cifraclub.com.br")

    def download(self, url: str) -> RawLyrics:
        soup = self._fetcher.get(url, self.SITE)
        cifra = self.parse(soup, url)
        slugs = _path_parts(url)
        if slugs is not None:
            equivalent = f"https://www.letras.mus.br/{slugs[0]}/{slugs[1]}/"
            try:
                letras = self._letras.download(equivalent)
            except DownloadError:
                return cifra
            if normalize_search(letras.title) == normalize_search(cifra.title):
                return letras
        return cifra

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
