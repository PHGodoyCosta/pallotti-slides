"""PDF → PNG pages (for the CLI preview and visual QA)."""

import shutil
import subprocess
from pathlib import Path

from pallotti_slides.presentation.errors import PdfConversionError
from pallotti_slides.presentation.pdf import PdfConverter

DEFAULT_DPI = 50
PNG_PREFIX = "slide"


def pdf_to_pngs(pdf: Path, folder: Path, dpi: int = DEFAULT_DPI) -> list[Path]:
    """Render every page of ``pdf`` as ``slide-01.png``… in ``folder`` (needs ``pdftoppm``)."""
    exe = shutil.which("pdftoppm")
    if exe is None:
        raise PdfConversionError(
            "pdftoppm não encontrado. Instale o poppler-utils para gerar as imagens da prévia."
        )
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob(f"{PNG_PREFIX}-*.png"):
        old.unlink()
    command = [exe, "-png", "-r", str(dpi), str(pdf), str(folder / PNG_PREFIX)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise PdfConversionError(f"Falha ao executar o pdftoppm: {error}") from error
    pages = sorted(folder.glob(f"{PNG_PREFIX}-*.png"))
    if result.returncode != 0 or not pages:
        raise PdfConversionError(f"O pdftoppm não gerou imagens de {pdf.name}. {result.stderr}")
    return pages


def render_preview(
    pptx: Path, folder: Path, converter: PdfConverter, dpi: int = DEFAULT_DPI
) -> list[Path]:
    """Convert ``pptx`` to PDF and then to one PNG per slide, all inside ``folder``."""
    pdf = converter.convert(pptx, folder)
    return pdf_to_pngs(pdf, folder, dpi)
