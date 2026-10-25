"""Use case: extract the data of a leaflet PDF (F2)."""

from dataclasses import dataclass
from pathlib import Path

from pallotti_slides.config import Paths
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Notice
from pallotti_slides.leaflet.errors import LeafletError
from pallotti_slides.leaflet.extractor import LeafletExtractor
from pallotti_slides.leaflet.schema import LeafletData
from pallotti_slides.llm.client import ClaudeClient
from pallotti_slides.llm.errors import LLMError

__all__ = [
    "LLMError",
    "LeafletError",
    "LeafletResult",
    "PallottiError",
    "extract_leaflet",
    "make_leaflet_extractor",
]


@dataclass(frozen=True)
class LeafletResult:
    """Extracted data plus a warning for each required field that is missing."""

    data: LeafletData
    notices: list[Notice]


def make_leaflet_extractor(cache_dir: Path | None = None) -> LeafletExtractor:
    """Real extractor; raises ``LLMError`` (Portuguese) when there is no API key."""
    folder = cache_dir if cache_dir is not None else Paths.default().data / "cache" / "leaflets"
    return LeafletExtractor(ClaudeClient.from_environment(), folder)


def extract_leaflet(pdf: Path, extractor: LeafletExtractor | None = None) -> LeafletResult:
    """Extract ``pdf``; a missing field becomes a ``Notice``, never an invented value."""
    data = (extractor or make_leaflet_extractor()).extract(pdf)
    notices = [
        Notice(level="warning", message=f"Não encontrei no folheto: {label}.", field=label)
        for label in data.missing_fields()
    ]
    notices.extend(Notice(level="info", message=note) for note in data.notes)
    return LeafletResult(data=data, notices=notices)
