import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from songs.fakes import FakeDownloader, FakeLLM, raw

from pallotti_slides.application.container import Container
from pallotti_slides.application.new_mass import (
    LiturgyFields,
    NewMassService,
    assemble_mass,
    extracted_fields,
    mass_notices,
)
from pallotti_slides.db.repositories import SongRepository
from pallotti_slides.db.session import apply_migrations, make_engine, session_factory
from pallotti_slides.domain.enums import (
    EucharisticPrayer,
    LiturgicalSeason,
    SongMoment,
    SongSource,
    StanzaType,
)
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Line, Song, Stanza
from pallotti_slides.leaflet.schema import LeafletData
from pallotti_slides.songs.parser import ChorusDetector, LyricsParser
from pallotti_slides.songs.repertoire import RepertoireImporter
from pallotti_slides.songs.resolver import SongResolver
from pallotti_slides.songs.web_search import SongCandidate, WebSongSearcher

HTML = Path(__file__).resolve().parents[2] / "fixtures/html/cifra_club/repertorio_57846361.html"
URL = "https://www.letras.mus.br/a/b/"
LYRICS = "Ó Senhor\nVem nos salvar\n\nNós queremos\nTe louvar"
DATE = dt.date(2026, 10, 25)


def song(title: str = "Canto", url: str | None = None) -> Song:
    return Song(
        title=title,
        source=SongSource.MANUAL,
        source_url=url,
        stanzas=[Stanza(id=1, type=StanzaType.VERSE, lines=[Line(text="Ó Senhor")])],
        order=[1],
    )


def full_fields(**changes: Any) -> LiturgyFields:
    base = LiturgyFields(
        title="30° Domingo do Tempo Comum",
        first_reading="Ex 22,20-26",
        psalm_number="17(18)",
        psalm_refrain="Eu vos amo, Senhor.",
        gospel="Mt 22,34-40",
        intercessions_response="Senhor, escutai-nos.",
        eucharistic_prayer=EucharisticPrayer.III,
        mystery_of_faith="Anunciamos, Senhor, a vossa morte.",
    )
    return LiturgyFields(**{**base.__dict__, **changes})


class FakeExtractor:
    def __init__(self, data: LeafletData | None = None) -> None:
        self.data = data

    def extract(self, pdf: Path) -> LeafletData:
        if self.data is None:
            raise PallottiError("Sem chave de API.")
        return self.data


class FakeInterpreter:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def interpret(self, text: str) -> list[Any]:
        if self.fail:
            raise PallottiError("Falhou.")
        return []


def service(tmp_path: Path, extractor: FakeExtractor | None = None, **extra: Any) -> NewMassService:
    engine = make_engine(f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    apply_migrations(engine)
    repo = SongRepository(session_factory(engine)())
    llm = FakeLLM()
    downloader = FakeDownloader({URL: raw("Canto da web", URL, LYRICS)})
    resolver = SongResolver(
        repo, [downloader], LyricsParser(ChorusDetector()), WebSongSearcher(llm)
    )
    container = SimpleNamespace(
        leaflet_extractor=extractor or FakeExtractor(),
        interpreter=FakeInterpreter(),
        repertoire_importer=RepertoireImporter(fetch=lambda _u: HTML.read_text(encoding="utf-8")),
        resolver=resolver,
        song_repo=repo,
        template=SimpleNamespace(available_prayers=lambda: [EucharisticPrayer.III]),
        **extra,
    )
    return NewMassService(cast(Container, container))


def test_default_date_is_next_sunday(tmp_path: Path) -> None:
    svc = service(tmp_path)
    assert svc.default_date(dt.date(2026, 10, 21)) == dt.date(2026, 10, 25)
    assert svc.default_date(DATE) == DATE
    assert svc.available_prayers() == [EucharisticPrayer.III]


def test_assemble_mass_needs_a_prayer() -> None:
    mass, notices = assemble_mass(DATE, full_fields(eucharistic_prayer=None), True, {})
    assert mass is None
    assert [n.field for n in notices] == ["liturgy.eucharistic_prayer"]


def test_assemble_mass_reports_empty_required_fields() -> None:
    mass, notices = assemble_mass(DATE, full_fields(gospel="  "), True, {})
    assert mass is not None
    assert any(n.level == "error" and n.field == "liturgy.gospel" for n in notices)
    assert mass.liturgy.second_reading is None


def test_mass_notices_gloria_remarks() -> None:
    fields = full_fields(season=LiturgicalSeason.LENT)
    mass, _ = assemble_mass(DATE, fields, False, {SongMoment.GLORIA: song()})
    assert mass is not None
    assert any(n.field == "songs.gloria" and n.level == "warning" for n in mass_notices(mass))
    clean, notices = assemble_mass(DATE, full_fields(), True, {SongMoment.ENTRANCE: song()})
    assert clean is not None
    assert not [n for n in notices if n.level == "error"]


def test_fields_from_leaflet_and_extracted() -> None:
    data = LeafletData(title="X", gospel="Mt 1", eucharistic_prayer=EucharisticPrayer.II)
    fields = LiturgyFields.from_leaflet(data)
    assert fields.title == "X"
    assert fields.first_reading == ""
    assert extracted_fields(data) == {"title", "gospel", "eucharistic_prayer"}


def test_process_inputs_stages_are_independent(tmp_path: Path) -> None:
    svc = service(tmp_path)  # extractor fails: the repertoire must still be read
    steps: list[str] = []
    result = svc.process_inputs(
        DATE, Path("folheto.pdf"), "", "https://www.cifraclub.com.br/x/", steps.append
    )
    assert result.leaflet is None
    assert any(n.field == "leaflet" and n.level == "error" for n in result.notices)
    assert result.proposal is not None
    assert result.proposal.requires_confirmation
    assert steps  # progress was reported


def test_process_inputs_warns_about_date_mismatch(tmp_path: Path) -> None:
    data = LeafletData(title="X", date=dt.date(2026, 11, 1))
    svc = service(tmp_path, FakeExtractor(data))
    result = svc.process_inputs(DATE, Path("f.pdf"), "", "", lambda _t: None)
    assert result.leaflet == data
    assert any(n.field == "date" for n in result.notices)


def test_bad_repertoire_link_is_a_notice(tmp_path: Path) -> None:
    result = service(tmp_path).process_inputs(DATE, None, "", "https://exemplo.com/x", print)
    assert result.proposal is None
    assert [n.field for n in result.notices] == ["repertoire"]


def test_resolve_many_keeps_going_after_a_failure(tmp_path: Path) -> None:
    svc = service(tmp_path)
    results = svc.resolve_many(
        {SongMoment.ENTRANCE: URL, SongMoment.COMMUNION: LYRICS, SongMoment.MANTRA: "ninguém"},
        lambda _t: None,
    )
    assert results[SongMoment.ENTRANCE].origin == "web"
    assert results[SongMoment.COMMUNION].origin == "pasted"
    assert results[SongMoment.MANTRA].song is None
    # asking again for the URL is served by the library
    assert svc.resolve_moment(SongMoment.OFFERTORY, URL).origin == "library"


def test_choose_candidate(tmp_path: Path) -> None:
    svc = service(tmp_path)
    result = svc.choose_candidate(
        SongMoment.ENTRANCE, "canto", SongCandidate(title="Canto da web", url=URL)
    )
    assert result.origin == "web"
    assert result.song is not None
    assert result.song.source_url == URL


def test_save_to_library_updates_then_adds(tmp_path: Path) -> None:
    svc = service(tmp_path)
    resolved = svc.resolve_moment(SongMoment.ENTRANCE, URL).song
    assert resolved is not None
    edited = resolved.model_copy(update={"title": "Título corrigido"})
    assert "atualizado" in svc.save_to_library(edited)
    assert "adicionado" in svc.save_to_library(song("Outro canto"))
    repo = cast(Any, svc)._container.song_repo
    assert sorted(s.title for _id, s in repo.list_all()) == ["Outro canto", "Título corrigido"]


def test_generate_creates_the_folder(tmp_path: Path) -> None:
    calls: list[Path] = []

    def generate(_mass: object, folder: Path) -> str:
        calls.append(folder)
        return "ok"

    svc = service(tmp_path, generator=SimpleNamespace(generate=generate))
    mass, _ = assemble_mass(DATE, full_fields(), True, {})
    assert mass is not None
    assert svc.generate(mass, tmp_path / "saida" / "x", lambda _t: None) == "ok"
    assert (tmp_path / "saida" / "x").is_dir()
    assert calls == [tmp_path / "saida" / "x"]
