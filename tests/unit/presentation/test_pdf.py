"""PDF conversion and PNG rendering: error paths that need neither LibreOffice nor poppler."""

from pathlib import Path

import pytest

from pallotti_slides.presentation.errors import PdfConversionError
from pallotti_slides.presentation.pdf import LibreOfficeConverter, PdfConverter
from pallotti_slides.presentation.preview import pdf_to_pngs, render_preview


class FakePdfConverter:
    """Writes a placeholder file; stands in for LibreOffice."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, Path]] = []

    def convert(self, pptx: Path, folder: Path) -> Path:
        self.calls.append((pptx, folder))
        folder.mkdir(parents=True, exist_ok=True)
        pdf = folder / f"{pptx.stem}.pdf"
        pdf.write_bytes(b"%PDF-fake")
        return pdf


def test_fake_converter_satisfies_the_protocol() -> None:
    converter: PdfConverter = FakePdfConverter()
    assert converter is not None


def test_libreoffice_missing_is_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)
    with pytest.raises(PdfConversionError, match="LibreOffice não encontrado"):
        LibreOfficeConverter().convert(tmp_path / "a.pptx", tmp_path / "out")


def test_pdftoppm_missing_is_a_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(PdfConversionError, match="pdftoppm não encontrado"):
        pdf_to_pngs(tmp_path / "a.pdf", tmp_path / "png")


def test_render_preview_converts_first_and_stops_on_bad_pdf(tmp_path: Path) -> None:
    converter = FakePdfConverter()
    pptx = tmp_path / "m.pptx"
    pptx.write_bytes(b"x")
    with pytest.raises(PdfConversionError, match="não gerou imagens"):
        render_preview(pptx, tmp_path / "out", converter)
    assert converter.calls == [(pptx, tmp_path / "out")]
