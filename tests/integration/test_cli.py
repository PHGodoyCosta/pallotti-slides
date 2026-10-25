"""Every ``pallotti`` command: ``--help`` and a run with fakes (F15)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pallotti_slides.cli import app

ROOT = Path(__file__).resolve().parents[2]
MASS = ROOT / "tests" / "fixtures" / "masses" / "26tc_2026.json"

runner = CliRunner()

COMMANDS = [
    ["generate"],
    ["leaflet", "extract"],
    ["template", "inspect"],
    ["template", "preview"],
    ["doctor"],
    ["history", "list"],
    ["history", "show"],
]


@pytest.mark.parametrize("command", COMMANDS, ids=lambda c: " ".join(c))
def test_help(command: list[str]) -> None:
    res = runner.invoke(app, [*command, "--help"])
    assert res.exit_code == 0, res.output
    assert "Usage" in res.output


@pytest.mark.parametrize("group", ["leaflet", "template", "history"])
def test_group_help(group: str) -> None:
    res = runner.invoke(app, [group, "--help"])
    assert res.exit_code == 0, res.output


def test_history_list_empty() -> None:
    res = runner.invoke(app, ["history", "list"])
    assert res.exit_code == 0, res.output
    assert "Nenhuma missa" in res.output


def test_history_show_missing_exits_one() -> None:
    res = runner.invoke(app, ["history", "show", "999"])
    assert res.exit_code == 1
    assert "não encontrada" in res.output


def test_generate_then_history(tmp_path: Path) -> None:
    out = tmp_path / "saida"
    res = runner.invoke(app, ["generate", "--mass", str(MASS), "--output", str(out), "--no-pdf"])
    assert res.exit_code == 0, res.output
    assert list(out.glob("*.pptx"))

    listing = runner.invoke(app, ["history", "list"])
    assert listing.exit_code == 0, listing.output
    assert "26° Domingo do Tempo Comum" in listing.output
    assert "OE III" in listing.output

    shown = runner.invoke(app, ["history", "show", "1"])
    assert shown.exit_code == 0, shown.output
    saved = json.loads(shown.stdout)
    assert saved == json.loads(
        json.dumps(json.loads(MASS.read_text(encoding="utf-8")), ensure_ascii=False)
    )


def test_generate_invalid_mass_exits_one(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    res = runner.invoke(app, ["generate", "--mass", str(bad), "--output", str(tmp_path / "o")])
    assert res.exit_code == 1
    assert "ERRO" in res.output


def test_doctor_runs() -> None:
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0, res.output
