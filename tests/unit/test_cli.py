from pathlib import Path

import pytest
from typer.testing import CliRunner

from pallotti_slides import __version__
from pallotti_slides.cli import app

runner = CliRunner()


def test_help() -> None:
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "doctor" in res.output


def test_diagnose_exits_zero_and_lists_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PALLOTTI_FONTS_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("PATH", str(tmp_path))  # no soffice, no fc-match
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0
    assert __version__ in res.output
    assert "Python:" in res.output
    assert "LibreOffice (soffice): NÃO encontrado" in res.output
    assert "Aptos regular: NÃO encontrado" in res.output


def test_diagnose_with_font(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "Aptos.ttf").write_bytes(b"")
    (tmp_path / "Aptos-Bold.ttf").write_bytes(b"")
    monkeypatch.setenv("PALLOTTI_FONTS_DIR", str(tmp_path))
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0
    assert str(tmp_path / "Aptos.ttf") in res.output
    assert str(tmp_path / "Aptos-Bold.ttf") in res.output
