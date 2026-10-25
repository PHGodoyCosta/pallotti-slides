import json
import shutil
from pathlib import Path

import pytest

from pallotti_slides.leaflet.errors import LeafletError
from pallotti_slides.leaflet.extractor import LeafletExtractor
from pallotti_slides.leaflet.schema import LeafletData
from pallotti_slides.llm.client import FakeLLMClient

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
PDF = FIXTURES / "leaflets" / "30tc_2026.pdf"
EXPECTED = FIXTURES / "leaflets" / "30tc_2026.expected.json"
RECORDED = FIXTURES / "llm"


def test_extract_matches_expected(tmp_path: Path) -> None:
    extractor = LeafletExtractor(FakeLLMClient(RECORDED), tmp_path / "cache")
    data = extractor.extract(PDF)
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    actual = json.loads(data.model_dump_json())
    for key, value in expected.items():
        assert actual[key] == value, key


def test_title_is_normalized(tmp_path: Path) -> None:
    data = LeafletExtractor(FakeLLMClient(RECORDED), tmp_path).extract(PDF)
    assert data.title == "30° Domingo do Tempo Comum"


def test_second_call_uses_cache(tmp_path: Path) -> None:
    fake = FakeLLMClient(RECORDED)
    extractor = LeafletExtractor(fake, tmp_path / "cache")
    first = extractor.extract(PDF)
    second = LeafletExtractor(fake, tmp_path / "cache").extract(PDF)
    assert len(fake.calls) == 1
    assert second == first
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1


def test_corrupt_cache_is_redone(tmp_path: Path) -> None:
    fake = FakeLLMClient(RECORDED)
    extractor = LeafletExtractor(fake, tmp_path)
    extractor.extract(PDF)
    next(tmp_path.glob("*.json")).write_text("{ruim", encoding="utf-8")
    assert extractor.extract(PDF).first_reading == "Ex 22,20-26"
    assert len(fake.calls) == 2


def test_pdf_sent_with_no_invention_instruction(tmp_path: Path) -> None:
    fake = FakeLLMClient(RECORDED)
    LeafletExtractor(fake, tmp_path).extract(PDF)
    call = fake.calls[0]
    assert call["pdf"] == PDF.read_bytes()
    assert call["schema"] is LeafletData
    assert "null" in call["instruction"]
    assert "NUNCA invente" in call["instruction"]


def test_not_a_leaflet_gives_friendly_error(tmp_path: Path) -> None:
    other = tmp_path / "receita.pdf"
    other.write_bytes(b"%PDF-1.4 receita de bolo")
    import hashlib

    digest = hashlib.sha256(other.read_bytes()).hexdigest()
    folder = tmp_path / "rec"
    folder.mkdir()
    (folder / f"{digest}.json").write_text(
        json.dumps({"notes": ["Parece uma receita."]}), encoding="utf-8"
    )
    extractor = LeafletExtractor(FakeLLMClient(folder), tmp_path / "cache")
    with pytest.raises(LeafletError, match="não parece ser um folheto"):
        extractor.extract(other)
    assert not (tmp_path / "cache").exists()  # failures are not cached


def test_file_that_is_not_pdf(tmp_path: Path) -> None:
    text = tmp_path / "a.pdf"
    text.write_text("oi", encoding="utf-8")
    with pytest.raises(LeafletError, match="não é um PDF"):
        LeafletExtractor(FakeLLMClient(RECORDED), tmp_path).extract(text)


def test_missing_fields_listed() -> None:
    data = LeafletData(title="X", gospel="Mt 1,1")
    assert "1ª leitura" in data.missing_fields()
    assert "Evangelho" not in data.missing_fields()
    assert "2ª leitura" not in data.missing_fields()
    assert not data.is_empty()
    assert LeafletData(notes=["?"]).is_empty()


def test_fixture_copy_is_stable(tmp_path: Path) -> None:
    copy = tmp_path / "outra.pdf"
    shutil.copy(PDF, copy)  # same bytes => same recorded response
    assert LeafletExtractor(FakeLLMClient(RECORDED), tmp_path / "c").extract(copy).psalm_number == (
        "17(18)"
    )
