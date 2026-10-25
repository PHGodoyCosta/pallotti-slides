"""Fatal errors of the presentation layer; ``PallottiError`` comes from the domain base."""

from pallotti_slides.domain.errors import PallottiError


class TemplateError(PallottiError):
    """The PowerPoint template is missing, unreadable or invalid."""


class PdfConversionError(PallottiError):
    """The .pptx → PDF (or PDF → PNG) conversion failed."""
