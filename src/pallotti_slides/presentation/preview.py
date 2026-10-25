"""PDF → PNG pages, page count and contact sheets (CLI preview and visual QA)."""

import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageDraw

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


_PAGES_LINE = re.compile(r"^Pages:\s+(\d+)", re.MULTILINE)
_PAGE_OBJECT = re.compile(rb"/Type\s*/Page(?![s\w])")


def pdf_page_count(pdf: Path) -> int:
    """Number of pages of ``pdf`` (``pdfinfo`` when available, else counting page objects)."""
    exe = shutil.which("pdfinfo")
    if exe is not None:
        result = subprocess.run([exe, str(pdf)], capture_output=True, text=True, check=False)
        found = _PAGES_LINE.search(result.stdout)
        if result.returncode == 0 and found:
            return int(found.group(1))
    return len(_PAGE_OBJECT.findall(pdf.read_bytes()))


def contact_sheet(pages: Sequence[Path], destination: Path, columns: int = 6) -> Path:
    """Paste ``pages`` (PNG) in a numbered grid; used to look at a whole deck at once."""
    if not pages:
        raise PdfConversionError("Nenhuma imagem para montar a grade.")
    images = [Image.open(page).convert("RGB") for page in pages]
    width, height = images[0].size
    gap, label = 6, 14
    rows = -(-len(images) // columns)
    sheet = Image.new(
        "RGB",
        (columns * (width + gap) + gap, rows * (height + label + gap) + gap),
        "#9a9a9a",
    )
    draw = ImageDraw.Draw(sheet)
    for number, image in enumerate(images, start=1):
        row, column = divmod(number - 1, columns)
        x = gap + column * (width + gap)
        y = gap + row * (height + label + gap)
        draw.text((x + 2, y), str(number), fill="black")
        sheet.paste(image.resize((width, height)), (x, y + label))
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)
    return destination
