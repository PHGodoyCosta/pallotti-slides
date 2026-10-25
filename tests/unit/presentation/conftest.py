"""Fixtures of the presentation tests."""

from pathlib import Path

import pytest

from pallotti_slides.config import FontLocator, FoundFonts
from pallotti_slides.domain.models import Mass
from pallotti_slides.presentation.measurer import TextMeasurer
from pallotti_slides.presentation.template import MassTemplate

ROOT = Path(__file__).resolve().parents[3]
MASSES = ROOT / "tests" / "fixtures" / "masses"


@pytest.fixture(scope="session")
def aptos() -> FoundFonts:
    """Aptos regular and bold; tests that need exact metrics are skipped without it."""
    fonts = FontLocator().locate()
    if not fonts.complete:
        pytest.skip("Aptos não instalada (as medidas exatas dependem dela)")
    return fonts


@pytest.fixture(scope="session")
def measurer(aptos: FoundFonts) -> TextMeasurer:
    return TextMeasurer(aptos.regular, aptos.bold)


@pytest.fixture(scope="session")
def template() -> MassTemplate:
    return MassTemplate.load()


@pytest.fixture
def mass_26tc() -> Mass:
    return Mass.model_validate_json((MASSES / "26tc_2026.json").read_text(encoding="utf-8"))


@pytest.fixture
def mass_full() -> Mass:
    return Mass.model_validate_json((MASSES / "full_9_songs.json").read_text(encoding="utf-8"))
