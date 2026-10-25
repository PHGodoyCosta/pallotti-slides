"""PDF conversion (ARQUITETURA §5). M2 has only the LibreOffice converter; M3 completes it."""

import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from pallotti_slides.config import locate_soffice
from pallotti_slides.presentation.errors import PdfConversionError

CONVERSION_TIMEOUT_SECONDS = 300


class PdfConverter(Protocol):
    """Converts a ``.pptx`` into a PDF inside ``folder`` and returns the PDF path."""

    def convert(self, pptx: Path, folder: Path) -> Path: ...


class LibreOfficeConverter:
    """``soffice --headless`` with a throw-away profile, so it never clashes with an open app."""

    def __init__(self, soffice: Path | None = None) -> None:
        self._soffice = soffice

    def convert(self, pptx: Path, folder: Path) -> Path:
        soffice = locate_soffice(self._soffice)
        if soffice is None:
            raise PdfConversionError(
                "LibreOffice não encontrado. Instale o LibreOffice para gerar o PDF."
            )
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pallotti-lo-") as profile:
            command = [
                str(soffice),
                f"-env:UserInstallation={Path(profile).as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(folder),
                str(pptx),
            ]
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=CONVERSION_TIMEOUT_SECONDS,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as error:
                raise PdfConversionError(f"Falha ao executar o LibreOffice: {error}") from error
        pdf = folder / f"{pptx.stem}.pdf"
        if result.returncode != 0 or not pdf.is_file():
            detail = (result.stderr or result.stdout).strip()
            raise PdfConversionError(f"O LibreOffice não gerou o PDF de {pptx.name}. {detail}")
        return pdf
