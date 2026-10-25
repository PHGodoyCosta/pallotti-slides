"""Real-API check of the leaflet extraction (run with ``pytest -m live``)."""

import json
import os
from pathlib import Path

import pytest

from pallotti_slides.leaflet.extractor import LeafletExtractor
from pallotti_slides.llm.client import ClaudeClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "leaflets"
KEY_FIELDS = (
    "title",
    "first_reading",
    "gospel",
    "second_reading",
    "psalm_number",
    "psalm_refrain",
    "intercessions_response",
    "eucharistic_prayer",
    "mystery_of_faith",
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="sem ANTHROPIC_API_KEY"),
]


@pytest.mark.parametrize("pdf", sorted(FIXTURES.glob("*.pdf")), ids=lambda p: p.stem)
def test_key_fields_are_exact(pdf: Path, tmp_path: Path) -> None:
    expected = json.loads(pdf.with_suffix(".expected.json").read_text(encoding="utf-8"))
    data = LeafletExtractor(ClaudeClient.from_environment(), tmp_path).extract(pdf)
    actual = json.loads(data.model_dump_json())
    wrong = {k: (actual[k], expected[k]) for k in KEY_FIELDS if actual[k] != expected[k]}
    assert not wrong
