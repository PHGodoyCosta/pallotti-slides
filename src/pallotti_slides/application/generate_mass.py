"""Use case: generate the .pptx and .pdf of a Mass (SPEC F8, F9, F11).

Minimal version of M3; M8 adds the history (``mass_repo``) and the container.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pallotti_slides.config import FontLocator, TypographyConfig
from pallotti_slides.db.repositories import MassFiles
from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Mass, Notice
from pallotti_slides.domain.rules import output_file_name, validate_mass
from pallotti_slides.presentation.builder import PptxBuilder
from pallotti_slides.presentation.errors import PdfConversionError, TemplateError
from pallotti_slides.presentation.measurer import TextMeasurer
from pallotti_slides.presentation.paginator import SongPage, SongPaginator
from pallotti_slides.presentation.pdf import LibreOfficeConverter, PdfConverter
from pallotti_slides.presentation.planner import BuildPlanner
from pallotti_slides.presentation.template import MassTemplate

PDF_HELP = (
    "O PowerPoint foi gerado, mas o PDF não. Instale o LibreOffice "
    "(https://pt-br.libreoffice.org) e gere de novo, ou abra o .pptx no PowerPoint e use "
    "Arquivo → Exportar → PDF."
)


class MassHistory(Protocol):
    """Where generated Masses are recorded (``db.MassRepository``; wired in M8)."""

    def save(self, mass: Mass, files: MassFiles | None = None) -> int: ...


@dataclass(frozen=True)
class GenerationResult:
    """Generated files; ``pdf`` is ``None`` when the conversion was not possible."""

    pptx: Path
    pdf: Path | None
    notices: list[Notice] = field(default_factory=list)


class MassGenerator:
    """Mass -> song pages -> slide plan -> .pptx -> .pdf."""

    def __init__(
        self,
        template: MassTemplate,
        paginator: SongPaginator,
        planner: BuildPlanner,
        builder: PptxBuilder,
        converter: PdfConverter | None,
        mass_repo: MassHistory | None = None,
    ) -> None:
        self._template = template
        self._paginator = paginator
        self._planner = planner
        self._builder = builder
        self._converter = converter
        self._mass_repo = mass_repo

    def generate(self, mass: Mass, output_dir: Path) -> GenerationResult:
        errors = [n for n in validate_mass(mass) if n.level == "error"]
        if errors:
            details = " ".join(notice.message for notice in errors)
            raise PallottiError(f"Não é possível gerar a missa: {details}")
        template_errors = [n for n in self._template.validate() if n.level == "error"]
        if template_errors:
            details = " ".join(notice.message for notice in template_errors)
            raise TemplateError(f"O modelo do PowerPoint tem problemas: {details}")

        notices = list(self._paginator.measurer.notices)
        pages = self._paginate(mass, notices)
        plan = self._planner.plan(self._template, mass, pages)

        name = output_file_name(mass)
        pptx = self._builder.build(self._template.path, plan, output_dir / f"{name}.pptx")

        pdf: Path | None = None
        if self._converter is None:
            notices.append(Notice(level="info", message="PDF não solicitado."))
        else:
            try:
                pdf = self._converter.convert(pptx, output_dir)
            except PdfConversionError as error:
                notices.append(Notice(level="warning", message=f"{error} {PDF_HELP}"))
        if self._mass_repo is not None:
            self._mass_repo.save(mass, MassFiles(pptx=pptx, pdf=pdf))
        return GenerationResult(pptx=pptx, pdf=pdf, notices=notices)

    def _paginate(self, mass: Mass, notices: list[Notice]) -> dict[SongMoment, list[SongPage]]:
        pages: dict[SongMoment, list[SongPage]] = {}
        measurer = self._paginator.measurer
        for moment in SongMoment:
            song = mass.songs.get(moment)
            if song is None or (moment is SongMoment.GLORIA and not mass.has_gloria):
                continue
            area = self._template.song_area(moment)
            body = self._template.body_format(moment)
            song_pages = self._paginator.paginate(song, area, body)
            if not song_pages:
                notices.append(
                    Notice(
                        level="warning",
                        message=f"O canto de {moment.label} está sem letra e foi omitido.",
                        field=f"songs.{moment.value}",
                    )
                )
                continue
            if not all(measurer.fits(p.lines, p.size_pt, area, body) for p in song_pages):
                notices.append(
                    Notice(
                        level="warning",
                        message=(
                            f"Uma linha do canto de {moment.label} é longa demais e pode sair "
                            "da área do slide; revise a letra."
                        ),
                        field=f"songs.{moment.value}",
                    )
                )
            pages[moment] = song_pages
        return pages


def make_mass_generator(
    template_path: Path | None = None,
    *,
    with_pdf: bool = True,
    typography: TypographyConfig | None = None,
) -> MassGenerator:
    """Generator with the real dependencies (template, Aptos via ``FontLocator``, LibreOffice)."""
    template = MassTemplate.load(template_path)
    fonts = FontLocator().locate()
    measurer = TextMeasurer(fonts.regular, fonts.bold)
    return MassGenerator(
        template=template,
        paginator=SongPaginator(measurer, typography or TypographyConfig()),
        planner=BuildPlanner(),
        builder=PptxBuilder(),
        converter=LibreOfficeConverter() if with_pdf else None,
    )


def load_mass(path: Path) -> Mass:
    """Read a Mass saved as JSON (``tests/fixtures/masses/*.json``)."""
    try:
        return Mass.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise PallottiError(f"Não foi possível ler {path}: {error}") from error
    except ValueError as error:  # pydantic.ValidationError is a ValueError
        raise PallottiError(f"Arquivo de missa inválido ({path.name}): {error}") from error
