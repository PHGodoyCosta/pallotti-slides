"""Fake container for the Nova Missa page tests and screenshots (no network, no LLM)."""

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from pallotti_slides.application.container import Container
from pallotti_slides.application.generate_mass import GenerationResult
from pallotti_slides.domain.enums import EucharisticPrayer, LiturgicalSeason, SongSource, StanzaType
from pallotti_slides.domain.models import Line, Mass, Notice, Song, SongRequest, Stanza
from pallotti_slides.leaflet.schema import LeafletData
from pallotti_slides.songs.repertoire import RepertoireImporter
from pallotti_slides.songs.resolver import ResolutionResult
from pallotti_slides.songs.web_search import SongCandidate

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
REPERTOIRE_HTML = FIXTURES / "html" / "cifra_club" / "repertorio_57846361.html"
LEAFLET_PDF = FIXTURES / "leaflets" / "30tc_2026.pdf"
REPERTOIRE_URL = "https://www.cifraclub.com.br/@32936533/repertorio/57846361/"

LYRICS = "Eis-me aqui, Senhor\nPara fazer a tua vontade\n\nTu és minha vida\nOutro Deus não há"


def make_song(title: str, url: str | None = None) -> Song:
    return Song(
        title=title,
        artist="Autor",
        source=SongSource.MANUAL,
        source_url=url,
        stanzas=[
            Stanza(
                id=1,
                type=StanzaType.CHORUS,
                lines=[Line(text="Eis-me aqui, Senhor", bold=True), Line(text="Eis-me aqui")],
            ),
            Stanza(id=2, type=StanzaType.VERSE, lines=[Line(text="Tu és minha vida")]),
        ],
        order=[2, 1, 2, 1],
    )


class FakeResolver:
    """Resolves URLs and pasted lyrics; titles in ``AMBIGUOUS`` give candidates."""

    AMBIGUOUS = "ave"

    def __init__(self) -> None:
        self.requests: list[SongRequest] = []
        self.confirmed: list[SongCandidate] = []

    def resolve(self, request: SongRequest) -> ResolutionResult:
        self.requests.append(request)
        if request.kind == "title" and request.text.lower() == self.AMBIGUOUS:
            return ResolutionResult(
                song=None,
                origin="web",
                candidates=[
                    SongCandidate(title="Ave Maria", artist="Autor A", url="https://x/a/"),
                    SongCandidate(title="Ave Maria (Gounod)", artist="Autor B", song_id=7),
                ],
            )
        if request.kind == "title" and request.text.lower() == "nada":
            return ResolutionResult(
                song=None,
                origin="none",
                notices=[Notice(level="warning", message="Não encontrei «nada».")],
            )
        title = request.text.strip().rstrip("/").rsplit("/", 1)[-1] or request.text
        origin = {"url": "web", "lyrics": "pasted"}.get(request.kind, "library")
        return ResolutionResult(song=make_song(title), origin=origin)  # type: ignore[arg-type]

    def confirm(self, request: SongRequest, candidate: SongCandidate) -> Song:
        self.confirmed.append(candidate)
        return make_song(candidate.title)


class FakeSongRepo:
    def __init__(self) -> None:
        self.updated: list[tuple[int, Song]] = []
        self.added: list[Song] = []

    def by_url(self, url: str) -> None:
        return None

    def search(self, term: str, limit: int = 5) -> list[object]:
        return []

    def update(self, song_id: int, song: Song, **_kw: object) -> None:
        self.updated.append((song_id, song))

    def add(self, song: Song, lyrics: str, **_kw: object) -> int:
        self.added.append(song)
        return 1


class FakeGenerator:
    def __init__(self) -> None:
        self.masses: list[Mass] = []

    def generate(self, mass: Mass, folder: Path) -> GenerationResult:
        self.masses.append(mass)
        folder.mkdir(parents=True, exist_ok=True)
        pptx = folder / "Missa - teste.pptx"
        pptx.write_bytes(b"pptx")
        pdf = folder / "Missa - teste.pdf"
        shutil.copy(LEAFLET_PDF, pdf)
        return GenerationResult(pptx=pptx, pdf=pdf, notices=[])


class FakeExtractor:
    def __init__(self, data: LeafletData) -> None:
        self.data = data
        self.calls: list[Path] = []

    def extract(self, pdf: Path) -> LeafletData:
        self.calls.append(pdf)
        return self.data


class FakeInterpreter:
    def interpret(self, text: str) -> list[SongRequest]:
        return []


PARTIAL_LEAFLET = LeafletData(
    title="26° Domingo do Tempo Comum",
    season=LiturgicalSeason.ORDINARY_TIME,
    first_reading="Ez 18,25-28",
    psalm_number="24(25)",
    psalm_refrain="Recordai, Senhor meu Deus, vossa ternura e compaixão!",
    gospel="Mt 21,28-32",
    eucharistic_prayer=EucharisticPrayer.III,
)  # no intercessions response, no mystery of faith: those must be highlighted


def make_container(leaflet: LeafletData | None = None) -> Container:
    """A ``Container`` look-alike with just what the page needs."""
    html = REPERTOIRE_HTML.read_text(encoding="utf-8")
    fake = SimpleNamespace(
        template=SimpleNamespace(
            available_prayers=lambda: [EucharisticPrayer.II, EucharisticPrayer.III]
        ),
        leaflet_extractor=FakeExtractor(leaflet or PARTIAL_LEAFLET),
        interpreter=FakeInterpreter(),
        repertoire_importer=RepertoireImporter(fetch=lambda _url: html),
        resolver=FakeResolver(),
        song_repo=FakeSongRepo(),
        generator=FakeGenerator(),
        close=lambda: None,
    )
    return cast(Container, fake)
