"""Use cases behind the "Nova Missa" page: intake, song resolution, review and generation.

Everything here is plain Python (no Qt): the interface runs these calls inside a ``Task``.
Nothing is applied automatically: moments proposed by a link or by free text come back as
proposals for the user to confirm (SPEC F4).
"""

import datetime as dt
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pallotti_slides.application.container import Container
from pallotti_slides.application.generate_mass import GenerationResult
from pallotti_slides.application.leaflet_extraction import extract_leaflet
from pallotti_slides.application.song_requests import propose_repertoire
from pallotti_slides.domain.enums import EucharisticPrayer, LiturgicalSeason, SongMoment
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import (
    Celebration,
    Liturgy,
    Mass,
    Notice,
    Song,
    SongRequest,
)
from pallotti_slides.domain.rules import next_sunday, validate_mass
from pallotti_slides.leaflet.schema import LeafletData
from pallotti_slides.songs.parser import detect_request_kind
from pallotti_slides.songs.repertoire import ProposedSong, RepertoireProposal
from pallotti_slides.songs.web_search import SongCandidate

__all__ = [
    "IntakeResult",
    "LiturgyFields",
    "MomentResult",
    "NewMassService",
    "ProposedSong",
    "RepertoireProposal",
    "SongCandidate",
    "assemble_mass",
    "extracted_fields",
    "mass_notices",
]

Report = Callable[[str], None]
Origin = Literal["library", "web", "pasted", "none"]


@dataclass(frozen=True)
class LiturgyFields:
    """The liturgy form as typed; texts are plain strings, the prayer may still be unset."""

    title: str = ""
    short_title: str = ""
    season: LiturgicalSeason = LiturgicalSeason.ORDINARY_TIME
    year: Literal["A", "B", "C"] | None = None
    first_reading: str = ""
    psalm_number: str = ""
    psalm_refrain: str = ""
    second_reading: str = ""
    gospel: str = ""
    intercessions_response: str = ""
    eucharistic_prayer: EucharisticPrayer | None = None
    mystery_of_faith: str = ""

    @classmethod
    def from_leaflet(cls, data: LeafletData) -> "LiturgyFields":
        """Form values found in the leaflet; anything missing stays empty (never invented)."""
        return cls(
            title=data.title or "",
            season=data.season or LiturgicalSeason.ORDINARY_TIME,
            year=data.year,
            first_reading=data.first_reading or "",
            psalm_number=data.psalm_number or "",
            psalm_refrain=data.psalm_refrain or "",
            second_reading=data.second_reading or "",
            gospel=data.gospel or "",
            intercessions_response=data.intercessions_response or "",
            eucharistic_prayer=data.eucharistic_prayer,
            mystery_of_faith=data.mystery_of_faith or "",
        )

    @classmethod
    def from_mass(cls, mass: Mass) -> "LiturgyFields":
        celebration, liturgy = mass.celebration, mass.liturgy
        return cls(
            title=celebration.title,
            short_title=celebration.short_title or "",
            season=celebration.season,
            year=celebration.year,
            first_reading=liturgy.first_reading,
            psalm_number=liturgy.psalm_number,
            psalm_refrain=liturgy.psalm_refrain,
            second_reading=liturgy.second_reading or "",
            gospel=liturgy.gospel,
            intercessions_response=liturgy.intercessions_response,
            eucharistic_prayer=liturgy.eucharistic_prayer,
            mystery_of_faith=liturgy.mystery_of_faith,
        )


def extracted_fields(data: LeafletData) -> set[str]:
    """Names of the ``LiturgyFields`` attributes the leaflet provided."""
    found = LiturgyFields.from_leaflet(data)
    names = {
        "title",
        "first_reading",
        "psalm_number",
        "psalm_refrain",
        "second_reading",
        "gospel",
        "intercessions_response",
        "mystery_of_faith",
    }
    result = {name for name in names if getattr(found, name)}
    if data.eucharistic_prayer is not None:
        result.add("eucharistic_prayer")
    if data.season is not None:
        result.add("season")
    if data.year is not None:
        result.add("year")
    return result


def assemble_mass(
    date: dt.date,
    fields: LiturgyFields,
    has_gloria: bool,
    songs: dict[SongMoment, Song],
) -> tuple[Mass | None, list[Notice]]:
    """Build the ``Mass`` from the form. Without a prayer there is no Mass, only an error."""
    if fields.eucharistic_prayer is None:
        notice = Notice(
            level="error",
            message="Escolha a Oração Eucarística.",
            field="liturgy.eucharistic_prayer",
        )
        return None, [notice]
    mass = Mass(
        celebration=Celebration(
            title=fields.title.strip(),
            short_title=fields.short_title.strip() or None,
            date=date,
            season=fields.season,
            year=fields.year,
        ),
        liturgy=Liturgy(
            first_reading=fields.first_reading.strip(),
            psalm_number=fields.psalm_number.strip(),
            psalm_refrain=fields.psalm_refrain.strip(),
            second_reading=fields.second_reading.strip() or None,
            gospel=fields.gospel.strip(),
            intercessions_response=fields.intercessions_response.strip(),
            eucharistic_prayer=fields.eucharistic_prayer,
            mystery_of_faith=fields.mystery_of_faith.strip(),
        ),
        has_gloria=has_gloria,
        songs=dict(songs),
    )
    return mass, mass_notices(mass)


def mass_notices(mass: Mass) -> list[Notice]:
    """``validate_mass`` plus the song remarks of the review step."""
    notices = validate_mass(mass)
    gloria = mass.songs.get(SongMoment.GLORIA)
    if gloria is not None and not mass.has_gloria:
        notices.append(
            Notice(
                level="warning",
                message="Esta missa está sem Glória: o canto do Glória será ignorado nos slides.",
                field="songs.gloria",
            )
        )
    elif gloria is None and mass.has_gloria:
        notices.append(
            Notice(
                level="info",
                message="O Glória está ligado, mas não há canto para ele: o grupo será removido.",
                field="songs.gloria",
            )
        )
    missing = [
        m
        for m in SongMoment
        if m not in mass.songs and not (m is SongMoment.GLORIA and not mass.has_gloria)
    ]
    if mass.songs and missing:
        names = ", ".join(moment.label for moment in missing)
        notices.append(
            Notice(
                level="info",
                message=f"Sem canto (estes grupos serão removidos dos slides): {names}.",
                field="songs",
            )
        )
    if not mass.songs:
        notices.append(
            Notice(
                level="warning",
                message="Nenhum canto foi informado: os grupos de cantos serão removidos.",
                field="songs",
            )
        )
    return notices


@dataclass(frozen=True)
class MomentResult:
    """How the text of one moment was resolved; ``song`` is ``None`` while open or failed."""

    moment: SongMoment
    text: str
    song: Song | None
    origin: Origin
    candidates: list[SongCandidate] = field(default_factory=list)
    notices: list[Notice] = field(default_factory=list)


@dataclass(frozen=True)
class IntakeResult:
    """What the data step produced; ``requests`` and ``proposal`` still need confirmation."""

    leaflet: LeafletData | None
    requests: list[SongRequest]
    proposal: RepertoireProposal | None
    notices: list[Notice]


class NewMassService:
    """Facade of the Nova Missa page over the container (attributes read when needed)."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._lock = threading.RLock()  # the DB session is shared by the worker threads

    # -- small helpers -------------------------------------------------------------------

    def default_date(self, today: dt.date | None = None) -> dt.date:
        """The next Sunday (today when it is Sunday)."""
        return next_sunday(today or dt.date.today())

    def default_output_dir(self) -> Path:
        return Path.home() / "Pallotti Slides"

    def available_prayers(self) -> list[EucharisticPrayer]:
        """Only the prayers that exist in the PowerPoint template."""
        return list(self._container.template.available_prayers())

    # -- data step -----------------------------------------------------------------------

    def process_inputs(
        self,
        date: dt.date,
        leaflet: Path | None,
        free_text: str,
        repertoire_url: str,
        report: Report,
    ) -> IntakeResult:
        """Leaflet, free text and repertoire link; each stage fails on its own."""
        notices: list[Notice] = []
        data: LeafletData | None = None
        requests: list[SongRequest] = []
        proposal: RepertoireProposal | None = None
        with self._lock:
            if leaflet is not None:
                report(f"Lendo o folheto «{leaflet.name}»…")
                try:
                    result = extract_leaflet(leaflet, self._container.leaflet_extractor)
                except PallottiError as error:
                    notices.append(Notice(level="error", message=str(error), field="leaflet"))
                    report("Não consegui ler o folheto; preencha a liturgia à mão.")
                else:
                    data = result.data
                    notices.extend(result.notices)
                    if data.date is not None and data.date != date:
                        notices.append(
                            Notice(
                                level="warning",
                                message=(
                                    f"A data do folheto ({data.date:%d/%m/%Y}) é diferente da "
                                    f"data informada ({date:%d/%m/%Y})."
                                ),
                                field="date",
                            )
                        )
                    report("Folheto lido. Confira os campos na etapa Liturgia.")
            if free_text.strip():
                report("Interpretando o texto livre dos cantos…")
                try:
                    requests = list(self._container.interpreter.interpret(free_text))
                except PallottiError as error:
                    notices.append(Notice(level="error", message=str(error), field="free_text"))
                    report("Não consegui interpretar o texto livre.")
                else:
                    report(f"Texto livre: {len(requests)} canto(s) reconhecido(s).")
            if repertoire_url.strip():
                report("Lendo o repertório do link…")
                try:
                    proposal = propose_repertoire(
                        repertoire_url.strip(), self._container.repertoire_importer
                    )
                except PallottiError as error:
                    notices.append(Notice(level="error", message=str(error), field="repertoire"))
                    report("Não consegui ler o repertório; informe os cantos um a um.")
                else:
                    report(f"Repertório: {len(proposal.items)} canto(s) encontrado(s).")
        return IntakeResult(leaflet=data, requests=requests, proposal=proposal, notices=notices)

    # -- songs ---------------------------------------------------------------------------

    def resolve_moment(self, moment: SongMoment, text: str) -> MomentResult:
        """Library first, then the internet; open choices come back as candidates."""
        text = text.strip()
        request = SongRequest(moment=moment, text=text, kind=detect_request_kind(text))
        with self._lock:
            result = self._container.resolver.resolve(request)
        return MomentResult(
            moment=moment,
            text=text,
            song=result.song,
            origin=result.origin,
            candidates=list(result.candidates),
            notices=list(result.notices),
        )

    def resolve_many(
        self, assignments: dict[SongMoment, str], report: Report
    ) -> dict[SongMoment, MomentResult]:
        """Resolve each moment on its own; a failure never stops the others."""
        results: dict[SongMoment, MomentResult] = {}
        for moment, text in assignments.items():
            report(f"{moment.label}: procurando o canto…")
            try:
                result = self.resolve_moment(moment, text)
            except PallottiError as error:
                result = MomentResult(
                    moment=moment,
                    text=text,
                    song=None,
                    origin="none",
                    notices=[
                        Notice(level="error", message=str(error), field=f"songs.{moment.value}")
                    ],
                )
            results[moment] = result
            report(_outcome_message(result))
        return results

    def choose_candidate(
        self, moment: SongMoment, text: str, candidate: SongCandidate
    ) -> MomentResult:
        """Use the candidate the user picked (downloads and saves when it comes from the web)."""
        text = text.strip()
        request = SongRequest(moment=moment, text=text, kind=detect_request_kind(text))
        with self._lock:
            song = self._container.resolver.confirm(request, candidate)
        origin: Origin = "library" if candidate.song_id is not None else "web"
        return MomentResult(moment=moment, text=text, song=song, origin=origin)

    def save_to_library(self, song: Song) -> str:
        """Update the library copy of ``song`` (found by URL, then by exact title) or add it."""
        repo = self._container.song_repo
        with self._lock:
            song_id: int | None = None
            if song.source_url:
                hit = repo.by_url(song.source_url)
                song_id = hit[0] if hit else None
            if song_id is None:
                exact = [m for m in repo.search(song.title, limit=3) if m.score >= 100.0]
                song_id = exact[0].song_id if exact else None
            if song_id is not None:
                repo.update(song_id, song, reviewed=True)
                return f"«{song.title}» atualizado na biblioteca."
            lyrics = "\n\n".join("\n".join(line.text for line in s.lines) for s in song.stanzas)
            repo.add(song, lyrics, reviewed=True)
            return f"«{song.title}» adicionado à biblioteca."

    # -- generation ----------------------------------------------------------------------

    def generate(self, mass: Mass, output_dir: Path, report: Report) -> GenerationResult:
        """Write the .pptx/.pdf into ``output_dir`` (also recorded in the history)."""
        report("Montando o PowerPoint e o PDF… (pode levar alguns instantes)")
        output_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            return self._container.generator.generate(mass, output_dir)


def _outcome_message(result: MomentResult) -> str:
    label = result.moment.label
    if result.song is not None:
        where = {"library": "do banco", "web": "da internet", "pasted": "da letra colada"}
        return f"{label}: «{result.song.title}» ({where.get(result.origin, 'encontrado')})."
    if result.candidates:
        return f"{label}: encontrei {len(result.candidates)} possibilidade(s); escolha uma."
    if any(n.level == "error" for n in result.notices):
        return f"{label}: não foi possível obter o canto."
    return f"{label}: nada encontrado."
