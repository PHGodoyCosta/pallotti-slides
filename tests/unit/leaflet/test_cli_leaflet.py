from pathlib import Path

import pytest
from typer.testing import CliRunner

from pallotti_slides import cli
from pallotti_slides.application import leaflet_extraction
from pallotti_slides.config import Settings
from pallotti_slides.leaflet.extractor import LeafletExtractor
from pallotti_slides.llm import client as llm_client
from pallotti_slides.llm.client import FakeLLMClient

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
PDF = FIXTURES / "leaflets" / "30tc_2026.pdf"

runner = CliRunner()


def test_extract_prints_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    extractor = LeafletExtractor(FakeLLMClient(FIXTURES / "llm"), tmp_path)
    monkeypatch.setattr(cli, "make_leaflet_extractor", lambda: extractor)
    res = runner.invoke(cli.app, ["leaflet", "extract", str(PDF)])
    assert res.exit_code == 0, res.output
    assert "Título: 30° Domingo do Tempo Comum" in res.output
    assert "Salmo: 17(18)" in res.output
    assert "Oração eucarística: (não encontrado)" in res.output


def test_extract_without_key_is_friendly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(llm_client, "_keyring_get", lambda provider="anthropic": None)
    monkeypatch.setattr(leaflet_extraction, "load_settings", lambda: Settings())
    res = runner.invoke(cli.app, ["leaflet", "extract", str(PDF)])
    assert res.exit_code != 0
    assert "chave da API" in res.output
    assert "Traceback" not in res.output


def test_extract_missing_file() -> None:
    res = runner.invoke(cli.app, ["leaflet", "extract", "nao_existe.pdf"])
    assert res.exit_code != 0
