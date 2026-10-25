"""Chat-like panel that shows, step by step, what the program is doing (ARQUITETURA §11)."""

from typing import Literal

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, SmoothScrollArea, isDarkTheme

MessageKind = Literal["info", "question", "error"]

_PREFIX = {"info": "", "question": "Pergunta: ", "error": "Erro: "}
_COLOR = {"info": None, "question": "#7A1F2B", "error": "#C42B1C"}


class ProgressChat(SmoothScrollArea):  # type: ignore[misc]
    """Scrolling list of message bubbles; the newest is always visible."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._messages: list[tuple[str, MessageKind]] = []
        self._body = QWidget()
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)
        self.setWidget(self._body)
        self.setWidgetResizable(True)
        self.setStyleSheet("background: transparent; border: none;")
        self._body.setStyleSheet("background: transparent;")

    def add_message(self, text: str, kind: MessageKind = "info") -> None:
        """Append a bubble; ``question`` is highlighted and ``error`` shown in red."""
        if kind not in _PREFIX:
            raise ValueError(f"Tipo de mensagem desconhecido: {kind!r}")
        self._messages.append((text, kind))
        bubble = CardWidget()
        bubble.setProperty("kind", kind)
        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(14, 10, 14, 10)
        label = BodyLabel(_PREFIX[kind] + text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        color = _COLOR[kind]
        if color is not None:
            label.setStyleSheet(
                f"color: {'#E0A0A8' if kind == 'question' and isDarkTheme() else color};"
            )
        inner.addWidget(label)
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        QTimer.singleShot(0, self._scroll_to_end)

    def clear(self) -> None:
        """Remove every message."""
        self._messages.clear()
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def messages(self) -> list[tuple[str, MessageKind]]:
        """The messages shown so far, oldest first."""
        return list(self._messages)

    def _scroll_to_end(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())
