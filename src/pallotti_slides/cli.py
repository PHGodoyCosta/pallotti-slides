"""Command-line interface (``pallotti ...``)."""

import platform
from pathlib import Path
from typing import Annotated

import typer

from pallotti_slides import __version__
from pallotti_slides.application.leaflet_extraction import (
    PallottiError,
    extract_leaflet,
    make_leaflet_extractor,
)
from pallotti_slides.config import FontLocator, locate_soffice

app = typer.Typer(
    name="pallotti",
    help="Pallotti Slides: gera os slides da missa de domingo.",
    no_args_is_help=True,
    add_completion=False,
)


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
