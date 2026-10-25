"""Command-line interface (``pallotti ...``)."""

import platform
from pathlib import Path

import typer

from pallotti_slides import __version__
from pallotti_slides.config import FontLocator, locate_soffice

app = typer.Typer(
    name="pallotti",
    help="Pallotti Slides: gera os slides da missa de domingo.",
    no_args_is_help=True,
    add_completion=False,
)


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
