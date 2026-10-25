import pytest
from pytestqt.qtbot import QtBot

from pallotti_slides.ui.components.progress_chat import ProgressChat


def test_add_and_clear(qtbot: QtBot) -> None:
    chat = ProgressChat()
    qtbot.addWidget(chat)
    chat.add_message("Lendo o folheto")
    chat.add_message("Qual canto é este?", "question")
    chat.add_message("Falhou", "error")
    assert chat.messages() == [
        ("Lendo o folheto", "info"),
        ("Qual canto é este?", "question"),
        ("Falhou", "error"),
    ]
    chat.clear()
    assert chat.messages() == []


def test_unknown_kind_rejected(qtbot: QtBot) -> None:
    chat = ProgressChat()
    qtbot.addWidget(chat)
    with pytest.raises(ValueError):
        chat.add_message("x", "other")  # type: ignore[arg-type]
