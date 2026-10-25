from pallotti_slides.songs.downloaders import strip_chords


def test_chord_only_lines_are_removed() -> None:
    text = "  Am       G/B     C\nTe amarei, Senhor\nD7(9)  F#m  Bb\nEu só encontro a paz"
    assert strip_chords(text) == "Te amarei, Senhor\nEu só encontro a paz"


def test_bracketed_chords_are_removed() -> None:
    assert strip_chords("Te [Am]amarei, [G/B]Senhor") == "Te amarei, Senhor"
    assert strip_chords("[Am] [G]\nverso") == "verso"


def test_labelled_chord_lines_and_tablature_are_removed() -> None:
    text = "Intro: Am G C (2x)\ne|---0---3---|\nB|-1-----0---|\nLetra aqui\n[Solo] Em D"
    assert strip_chords(text) == "Letra aqui"


def test_lyrics_and_section_names_survive() -> None:
    text = "[Refrão]\nA graça de Deus\n\n\n\nMe dá a paz\nEm Cristo, a luz"
    assert strip_chords(text) == "[Refrão]\nA graça de Deus\n\nMe dá a paz\nEm Cristo, a luz"


def test_no_chord_left_in_synthetic_sheet() -> None:
    sheet = "Intro: C G\n\n   C        G\nSenhor, tem piedade\n   Am       F\nCristo, tem piedade\n"
    assert strip_chords(sheet) == "Senhor, tem piedade\nCristo, tem piedade"


# --- fetcher / blocking workaround (M7-a), no network ---------------------------------------

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from pallotti_slides.songs.downloaders import (  # noqa: E402
    CifraClubDownloader,
    DownloadError,
    LetrasMusDownloader,
)
from pallotti_slides.songs.fetcher import HttpReply, PageFetcher  # noqa: E402
from pallotti_slides.songs.repertoire import RepertoireImporter  # noqa: E402

_HTML = Path(__file__).resolve().parents[2] / "fixtures" / "html"
CIFRA_URL = "https://www.cifraclub.com.br/padre-zezinho/o-povo-de-deus/"
LETRAS_URL = "https://www.letras.mus.br/padre-zezinho/o-povo-de-deus/"
LETRAS_PAGE = (
    '<div class="head --lyric"><h1>O Povo de Deus</h1><h2>Padre Zezinho</h2></div>'
    '<div class="lyric-original"><p>Um povo<br>que caminha</p></div>'
)
CIFRA_PAGE = (
    "<h1>O Povo de Deus</h1><h2>Padre Zezinho</h2>"
    "<pre data-chord-content>Um povo\nque caminha</pre>"
)


class Net:
    """Fake transports: ``log`` records ``(transport, url)`` in call order."""

    def __init__(self, primary: dict[str, HttpReply], fallback: dict[str, HttpReply]) -> None:
        self.log: list[tuple[str, str]] = []
        self._pages = {"httpx": primary, "curl": fallback}

    def transport(self, name: str):
        def get(url: str) -> HttpReply:
            self.log.append((name, url))
            return self._pages[name].get(url, HttpReply(404, ""))

        return get

    def fetcher(self, sleeps: list[float] | None = None) -> PageFetcher:
        sink = sleeps if sleeps is not None else []
        return PageFetcher(
            self.transport("httpx"),
            self.transport("curl"),
            pause=1.0,
            sleep=sink.append,
            clock=lambda: 0.0,
        )


def test_cifra_tries_letras_then_cifra_then_browser_fallback() -> None:
    net = Net(
        primary={CIFRA_URL: HttpReply(403, "")},
        fallback={CIFRA_URL: HttpReply(200, CIFRA_PAGE)},
    )
    raw = CifraClubDownloader(net.fetcher()).download(CIFRA_URL)
    assert raw.text == "Um povo\nque caminha"
    assert net.log == [("httpx", LETRAS_URL), ("httpx", CIFRA_URL), ("curl", CIFRA_URL)]


def test_matching_letras_page_avoids_cifra_entirely() -> None:
    net = Net(primary={LETRAS_URL: HttpReply(200, LETRAS_PAGE)}, fallback={})
    raw = CifraClubDownloader(net.fetcher()).download(CIFRA_URL)
    assert raw.url == LETRAS_URL
    assert net.log == [("httpx", LETRAS_URL)]


def test_letras_with_other_title_is_ignored_after_cifra_title_check() -> None:
    other = LETRAS_PAGE.replace("O Povo de Deus", "Outra Musica")
    net = Net(
        primary={LETRAS_URL: HttpReply(200, other), CIFRA_URL: HttpReply(403, "")},
        fallback={CIFRA_URL: HttpReply(200, CIFRA_PAGE)},
    )
    raw = CifraClubDownloader(net.fetcher()).download(CIFRA_URL)
    assert raw.url == CIFRA_URL


def test_access_denied_page_triggers_fallback() -> None:
    net = Net(
        primary={CIFRA_URL: HttpReply(200, "<html>Access Denied</html>")},
        fallback={CIFRA_URL: HttpReply(200, CIFRA_PAGE)},
    )
    assert "caminha" in CifraClubDownloader(net.fetcher()).download(CIFRA_URL).text
    assert net.log[-1] == ("curl", CIFRA_URL)


def test_still_blocked_gives_friendly_error_asking_to_paste() -> None:
    net = Net(primary={CIFRA_URL: HttpReply(403, "")}, fallback={CIFRA_URL: HttpReply(403, "")})
    with pytest.raises(DownloadError, match="cole a letra"):
        CifraClubDownloader(net.fetcher()).download(CIFRA_URL)
    assert [name for name, _ in net.log] == ["httpx", "httpx", "curl"]


def test_not_blocked_does_not_use_fallback() -> None:
    net = Net(primary={LETRAS_URL: HttpReply(200, LETRAS_PAGE)}, fallback={})
    LetrasMusDownloader(net.fetcher()).download(LETRAS_URL)
    assert all(name == "httpx" for name, _ in net.log)


def test_pause_between_requests_to_same_site() -> None:
    sleeps: list[float] = []
    net = Net(primary={CIFRA_URL: HttpReply(403, "")}, fallback={CIFRA_URL: HttpReply(200, "ok")})
    assert net.fetcher(sleeps).get(CIFRA_URL, "Cifra Club") == "ok"
    assert sleeps == [1.0]


def test_repertoire_uses_same_fetcher_path() -> None:
    url = "https://www.cifraclub.com.br/@32936533/repertorio/57846361/"
    page = (_HTML / "cifra_club" / "repertorio_57846361.html").read_text(encoding="utf-8")
    net = Net(primary={url: HttpReply(403, "")}, fallback={url: HttpReply(200, page)})
    proposal = RepertoireImporter(fetcher=net.fetcher()).load(url)
    assert len(proposal.items) == 7
    assert net.log == [("httpx", url), ("curl", url)]


def test_repertoire_blocked_error_suggests_one_by_one() -> None:
    url = "https://www.cifraclub.com.br/@1/repertorio/2/"
    net = Net(primary={url: HttpReply(403, "")}, fallback={url: HttpReply(403, "")})
    with pytest.raises(DownloadError, match="um a um"):
        RepertoireImporter(fetcher=net.fetcher()).load(url)
