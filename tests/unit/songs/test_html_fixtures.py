"""Saved real HTML (tests/fixtures/html) -> expected structure, plus downloader behaviour."""

import json
import re
from pathlib import Path

import httpx
import pytest
import respx
from bs4 import BeautifulSoup

from pallotti_slides.domain.enums import SongSource
from pallotti_slides.domain.models import Song
from pallotti_slides.songs.downloaders import (
    USER_AGENT,
    CifraClubDownloader,
    DownloadError,
    LetrasMusDownloader,
    RawLyrics,
)
from pallotti_slides.songs.parser import ChorusDetector, LyricsParser

HTML = Path(__file__).resolve().parents[2] / "fixtures" / "html"
CIFRA_FILES = sorted(p for p in (HTML / "cifra_club").glob("*.html") if "__" in p.stem)
LETRAS_FILES = sorted((HTML / "letras_mus").glob("*.html"))


def _url(path: Path) -> str:
    artist, song = path.stem.split("__")
    host = "www.cifraclub.com.br" if path.parent.name == "cifra_club" else "www.letras.mus.br"
    return f"https://{host}/{artist}/{song}/"


def _raw(path: Path) -> RawLyrics:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    if path.parent.name == "cifra_club":
        return CifraClubDownloader.parse(soup, _url(path))
    return LetrasMusDownloader.parse(soup, _url(path))


def _page(path: Path) -> httpx.Response:
    return httpx.Response(200, text=path.read_text(encoding="utf-8"))


def test_fixtures_were_saved() -> None:
    assert len(CIFRA_FILES) == 7
    assert len(LETRAS_FILES) == 2


@pytest.mark.parametrize("path", CIFRA_FILES + LETRAS_FILES, ids=lambda p: p.stem)
def test_html_becomes_expected_structure(path: Path) -> None:
    expected = json.loads(path.with_suffix(".expected.json").read_text(encoding="utf-8"))
    song, _ = LyricsParser(ChorusDetector()).parse(_raw(path))
    assert song.model_dump(mode="json") == expected
    assert Song.model_validate(expected)  # the expected file is itself a valid Song


@pytest.mark.parametrize("path", CIFRA_FILES, ids=lambda p: p.stem)
def test_no_chord_or_label_is_left_in_cifra_text(path: Path) -> None:
    chord_line = re.compile(
        r"^(?:\s*[A-G][#b]?(?:m|maj|dim|sus|add)?[º°]?\d*(?:/[A-G][#b]?)?\.?)+$"
    )
    for line in _raw(path).text.splitlines():
        assert not chord_line.match(line), line
        assert "|" not in line, line
        assert "\u200b" not in line
        assert not re.search(r"\[(?!refr)|Parte \d+ de \d+|\.{2,}|_{2,}", line, re.IGNORECASE), line


def test_prolongations_are_cleaned_in_cifra() -> None:
    gloria = _raw(HTML / "cifra_club" / "catolicas__gloria-a-deus-nos-altos-ceus.html").text
    for word in ("libertados", "agradecemos", "perdoai", "clamor", "esplendor"):
        assert word in gloria
    ave = _raw(HTML / "cifra_club" / "chitaozinho-e-xororo__ave-maria.html").text
    assert ave.splitlines()[0].split() == ["Ave", "Maria"]


def test_cifra_metadata() -> None:
    raw = _raw(HTML / "cifra_club" / "padre-zezinho__um-coracao-para-amar.html")
    assert (raw.title, raw.artist, raw.source) == (
        "Um Coração Para Amar",
        "Padre Zezinho",
        SongSource.CIFRA_CLUB,
    )
    assert _raw(HTML / "cifra_club" / "catolicas__eis-me-aqui-senhor.html").artist is None


@respx.mock
def test_letras_downloader_fetches_with_identified_user_agent() -> None:
    path = LETRAS_FILES[0]
    route = respx.get(_url(path)).mock(return_value=_page(path))
    raw = LetrasMusDownloader().download(_url(path))
    assert raw.source is SongSource.LETRAS_MUS
    assert route.calls.last.request.headers["user-agent"] == USER_AGENT
    assert LetrasMusDownloader().supports(_url(path))
    assert not LetrasMusDownloader().supports(_url(CIFRA_FILES[0]))


@respx.mock
def test_cifra_prefers_letras_when_title_matches() -> None:
    cifra = HTML / "cifra_club" / "padre-zezinho__um-coracao-para-amar.html"
    letras = HTML / "letras_mus" / "padre-zezinho__um-coracao-para-amar.html"
    respx.get(_url(cifra)).mock(return_value=_page(cifra))
    respx.get(_url(letras)).mock(return_value=_page(letras))
    raw = CifraClubDownloader().download(_url(cifra))
    assert raw.source is SongSource.LETRAS_MUS
    assert raw.url == _url(letras)


@respx.mock
def test_cifra_falls_back_when_letras_title_differs() -> None:
    cifra = HTML / "cifra_club" / "padre-zezinho__um-coracao-para-amar.html"
    other = HTML / "letras_mus" / "padre-zezinho__o-povo-de-deus.html"  # another song
    respx.get(_url(cifra)).mock(return_value=_page(cifra))
    respx.get(_url(other).replace("o-povo-de-deus", "um-coracao-para-amar")).mock(
        return_value=_page(other)
    )
    raw = CifraClubDownloader().download(_url(cifra))
    assert raw.source is SongSource.CIFRA_CLUB
    assert raw.title == "Um Coração Para Amar"
    assert "Eis o que eu venho te dar" in raw.text


@respx.mock
def test_cifra_falls_back_when_letras_is_missing_or_blocked() -> None:
    cifra = HTML / "cifra_club" / "catolicas__eis-me-aqui-senhor.html"
    respx.get(_url(cifra)).mock(return_value=_page(cifra))
    respx.get("https://www.letras.mus.br/catolicas/eis-me-aqui-senhor/").mock(
        return_value=httpx.Response(404)
    )
    assert CifraClubDownloader().download(_url(cifra)).source is SongSource.CIFRA_CLUB
    respx.get("https://www.letras.mus.br/catolicas/eis-me-aqui-senhor/").mock(
        side_effect=httpx.ConnectTimeout("lento")
    )
    assert CifraClubDownloader().download(_url(cifra)).source is SongSource.CIFRA_CLUB


@respx.mock
@pytest.mark.parametrize(
    "outcome",
    [httpx.Response(403), httpx.Response(500), httpx.Response(404), httpx.ConnectError("x")],
)
def test_network_failures_become_download_error(outcome: httpx.Response | Exception) -> None:
    url = _url(CIFRA_FILES[0])
    if isinstance(outcome, Exception):
        respx.get(url).mock(side_effect=outcome)
    else:
        respx.get(url).mock(return_value=outcome)
    with pytest.raises(DownloadError) as error:
        CifraClubDownloader().download(url)
    assert "Cifra Club" in str(error.value)


@respx.mock
def test_page_without_lyrics_is_a_download_error() -> None:
    url = "https://www.letras.mus.br/a/b/"
    respx.get(url).mock(return_value=httpx.Response(200, text="<html><body>nada</body></html>"))
    with pytest.raises(DownloadError):
        LetrasMusDownloader().download(url)
