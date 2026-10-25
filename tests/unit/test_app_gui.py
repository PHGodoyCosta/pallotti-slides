import pytest

from pallotti_slides.ui.app import main


def test_main_only_informs(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0
    assert "Interface ainda não implementada (M9)" in capsys.readouterr().out
