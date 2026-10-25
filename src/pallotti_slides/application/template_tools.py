"""Template tools used by the CLI (``pallotti template inspect`` / ``preview``)."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Notice
from pallotti_slides.presentation.pdf import LibreOfficeConverter, PdfConverter
from pallotti_slides.presentation.preview import DEFAULT_DPI, render_preview
from pallotti_slides.presentation.template import TAG_PREFIX, MassTemplate, default_template_path

__all__ = ["PallottiError", "SlideRow", "TemplateReport", "TemplateTools"]


@dataclass(frozen=True)
class SlideRow:
    """One line of the inspector table."""

    number: int  # 1-based, as shown in PowerPoint
    tag: str
    fields: str


@dataclass(frozen=True)
class TemplateReport:
    """Result of inspecting the template."""

    path: Path
    rows: list[SlideRow]
    notices: list[Notice]
    prayers: list[str]

    @property
    def has_errors(self) -> bool:
        return any(notice.level == "error" for notice in self.notices)


class TemplateTools:
    """Inspect and preview the PowerPoint template."""

    def __init__(
        self,
        template_path: Path | None = None,
        converter: PdfConverter | None = None,
    ) -> None:
        self._path = template_path or default_template_path()
        self._converter = converter or LibreOfficeConverter()

    def inspect(self) -> TemplateReport:
        """Read the template and list its slides, tags and problems."""
        template = MassTemplate.load(self._path)
        rows = [
            SlideRow(
                number=slide.index + 1,
                tag=_tag_text(slide.tag.raw, slide.tag.explicit),
                fields=", ".join(sorted(slide.fields)),
            )
            for slide in template.slides
        ]
        return TemplateReport(
            path=self._path,
            rows=rows,
            notices=template.validate(),
            prayers=[prayer.value for prayer in template.available_prayers()],
        )

    def preview(self, output: Path, dpi: int = DEFAULT_DPI) -> list[Path]:
        """Render the template as PDF + one PNG per slide in ``output``; returns the PNGs."""
        MassTemplate.load(self._path)  # clear message if the file is missing or broken
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pallotti-preview-") as work:
            copy = Path(work) / "modelo.pptx"
            copy.write_bytes(self._path.read_bytes())
            return render_preview(copy, output, self._converter, dpi)


def _tag_text(raw: str, explicit: bool) -> str:
    if not explicit:
        return "(sem etiqueta)"
    return raw.removeprefix(TAG_PREFIX).strip() or raw
