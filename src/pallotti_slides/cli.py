"""Command-line interface (``pallotti ...``)."""

import platform
from pathlib import Path
from typing import Annotated

import typer

from pallotti_slides import __version__
from pallotti_slides.application.generate_mass import load_mass, make_mass_generator
from pallotti_slides.application.leaflet_extraction import (
    extract_leaflet,
    make_leaflet_extractor,
)
from pallotti_slides.application.template_tools import TemplateTools
from pallotti_slides.config import FontLocator, locate_soffice
from pallotti_slides.domain.errors import PallottiError

app = typer.Typer(
    name="pallotti",
    help="Pallotti Slides: gera os slides da missa de domingo.",
    no_args_is_help=True,
    add_completion=False,
)
template_app = typer.Typer(
    help="Inspeciona e pré-visualiza o modelo PowerPoint.",
    no_args_is_help=True,
)
app.add_typer(template_app, name="template")

TemplateOption = Annotated[
    Path | None,
    typer.Option(
        "--template",
        help="Modelo .pptx a usar (padrão: o modelo do programa).",
        dir_okay=False,
    ),
]


leaflet_app = typer.Typer(help="Folheto litúrgico (PDF).", no_args_is_help=True)
app.add_typer(leaflet_app, name="leaflet")


def _line(label: str, path: Path | None, hint: str) -> str:
    if path is None:
        return f"{label}: NÃO encontrado. {hint}"
    return f"{label}: {path}"


@app.callback(help="Pallotti Slides: gera os slides da missa de domingo.")
def main_callback() -> None:
    """Root callback; help text is set on the Typer app."""


@app.command(
    "doctor",
    help="Mostra versão, Python, LibreOffice e fonte Aptos (sai 0 mesmo se faltar algo).",
)
def diagnose() -> None:
    """Show version, Python, LibreOffice and Aptos font (exit 0 even if something is missing)."""
    fonts = FontLocator().locate()
    typer.echo(f"Pallotti Slides: {__version__}")
    typer.echo(f"Python: {platform.python_version()}")
    typer.echo(
        _line(
            "LibreOffice (soffice)",
            locate_soffice(),
            "Instale o LibreOffice para gerar o PDF.",
        )
    )
    font_hint = "Instale a Aptos (download gratuito da Microsoft) ou defina PALLOTTI_FONTS_DIR."
    typer.echo(_line("Aptos regular", fonts.regular, font_hint))
    typer.echo(_line("Aptos negrito", fonts.bold, font_hint))


@app.command(
    "generate",
    help="Gera o PowerPoint e o PDF de uma missa a partir de um arquivo JSON.",
)
def generate(
    mass: Annotated[
        Path,
        typer.Option("--mass", help="Arquivo JSON da missa.", exists=True, dir_okay=False),
    ],
    output: Annotated[Path, typer.Option("--output", help="Pasta de saída.", file_okay=False)],
    template: TemplateOption = None,
    pdf: Annotated[
        bool, typer.Option("--pdf/--no-pdf", help="Gerar também o PDF (LibreOffice).")
    ] = True,
) -> None:
    """Generate the .pptx (and .pdf) of a Mass; exit 1 on a fatal error."""
    try:
        generator = make_mass_generator(template, with_pdf=pdf)
        result = generator.generate(load_mass(mass), output)
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"PowerPoint: {result.pptx}")
    typer.echo(f"PDF: {result.pdf if result.pdf else '(não gerado)'}")
    for notice in result.notices:
        where = f" [{notice.field}]" if notice.field else ""
        typer.echo(f"{notice.level.upper()}{where}: {notice.message}", err=True)


_LEAFLET_FIELDS = (
    ("Título", "title"),
    ("Data", "date"),
    ("Tempo litúrgico", "season"),
    ("Ano", "year"),
    ("1ª leitura", "first_reading"),
    ("Salmo", "psalm_number"),
    ("Refrão do salmo", "psalm_refrain"),
    ("2ª leitura", "second_reading"),
    ("Evangelho", "gospel"),
    ("Refrão das preces", "intercessions_response"),
    ("Oração eucarística", "eucharistic_prayer"),
    ("Mistério da fé", "mystery_of_faith"),
)


@leaflet_app.command(
    "extract",
    help="Extrai os dados do folheto (PDF) com IA. Precisa da chave da API da Anthropic.",
)
def extract_leaflet_command(
    pdf: Annotated[
        Path, typer.Argument(help="Arquivo PDF do folheto.", exists=True, dir_okay=False)
    ],
) -> None:
    """Extract leaflet data and print it; exit code 1 on a fatal error."""
    try:
        result = extract_leaflet(pdf, make_leaflet_extractor())
    except PallottiError as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=1) from error
    for label, attribute in _LEAFLET_FIELDS:
        value = getattr(result.data, attribute)
        typer.echo(f"{label}: {value if value not in (None, '') else '(não encontrado)'}")
    for notice in result.notices:
        typer.echo(f"[{notice.level}] {notice.message}", err=True)


@template_app.command(
    "inspect",
    help="Lista os slides do modelo, suas etiquetas e problemas (sai 1 se houver erros).",
)
def template_inspect(template: TemplateOption = None) -> None:
    """Print the slide table and the problems of the template; exit 1 on errors."""
    try:
        report = TemplateTools(template).inspect()
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"Modelo: {report.path}")
    typer.echo(f"{'Slide':>5}  {'Etiqueta':<28}  Campos")
    for row in report.rows:
        typer.echo(f"{row.number:>5}  {row.tag:<28}  {row.fields}")
    typer.echo(f"Orações Eucarísticas: {', '.join(report.prayers) or 'nenhuma'}")
    for notice in report.notices:
        where = f" [{notice.field}]" if notice.field else ""
        typer.echo(f"{notice.level.upper()}{where}: {notice.message}")
    errors = sum(1 for notice in report.notices if notice.level == "error")
    typer.echo(f"{len(report.rows)} slides, {errors} erro(s).")
    if report.has_errors:
        raise typer.Exit(1)


@template_app.command(
    "preview",
    help="Gera um PNG por slide do modelo (precisa do LibreOffice e do pdftoppm).",
)
def template_preview(
    output: Annotated[Path, typer.Option("--output", help="Pasta de saída dos PNGs.")],
    template: TemplateOption = None,
) -> None:
    """Render the template to PNGs, one per slide."""
    try:
        pages = TemplateTools(template).preview(output)
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"{len(pages)} imagens em {output}")
