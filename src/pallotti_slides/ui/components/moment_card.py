"""Card of one song moment: input, state, candidates and "editar letra" (SPEC F4, F5, F7)."""

from typing import Literal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    CardWidget,
    FluentIcon,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    TransparentToolButton,
    isDarkTheme,
)

from pallotti_slides.application.new_mass import MomentResult, SongCandidate
from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import Song

StatusLevel = Literal["info", "ok", "warning", "error"]

_COLORS: dict[StatusLevel, str] = {
    "info": "#6B6B6B",
    "ok": "#1E7B34",
    "warning": "#B25E00",
    "error": "#C42B1C",
}
_DARK_COLORS: dict[StatusLevel, str] = {
    "info": "#B5B5B5",
    "ok": "#6CCB5F",
    "warning": "#FCB04C",
    "error": "#FF99A4",
}
_ORIGINS = {
    "library": "Do banco de cantos",
    "web": "Da internet (salvo no banco)",
    "pasted": "Letra colada (manual, salva no banco)",
}


class MomentCard(CardWidget):  # type: ignore[misc]
    """One card per moment of the Mass; emits requests, the page does the work."""

    resolve_requested = Signal(object, str)  # (SongMoment, text)
    candidate_chosen = Signal(object, object)  # (SongMoment, SongCandidate)
    edit_requested = Signal(object)  # SongMoment
    clear_requested = Signal(object)  # SongMoment

    def __init__(self, moment: SongMoment, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.moment = moment
        self.setObjectName(f"moment-card-{moment.value}")
        self._song: Song | None = None
        self._candidates: list[SongCandidate] = []
        self._candidate_buttons: list[PushButton] = []

        self.input = PlainTextEdit()
        self.input.setPlaceholderText("Título, link (Letras.mus.br / Cifra Club) ou a letra colada")
        self.input.setFixedHeight(64)
        self.search_button = PrimaryPushButton(FluentIcon.SEARCH, "Buscar")
        self.edit_button = PushButton(FluentIcon.EDIT, "Editar letra")
        self.clear_button = TransparentToolButton(FluentIcon.DELETE)
        self.clear_button.setToolTip("Remover o canto deste momento")
        self.title_label = StrongBodyLabel(moment.label)
        self.status_label = CaptionLabel("Sem canto")
        self.status_label.setWordWrap(True)
        self.hint_label = CaptionLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.hide()

        self.search_button.clicked.connect(self._emit_resolve)
        self.edit_button.clicked.connect(lambda: self.edit_requested.emit(self.moment))
        self.clear_button.clicked.connect(self._emit_clear)

        buttons = QVBoxLayout()
        buttons.setSpacing(6)
        buttons.addWidget(self.search_button)
        buttons.addWidget(self.edit_button)
        buttons.addStretch(1)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.input, 1)
        row.addLayout(buttons)

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.clear_button)

        self._candidates_box = QVBoxLayout()
        self._candidates_box.setSpacing(4)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addLayout(row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.hint_label)
        layout.addLayout(self._candidates_box)
        self.clear()

    # -- reading -------------------------------------------------------------------------

    def text(self) -> str:
        return str(self.input.toPlainText()).strip()

    def song(self) -> Song | None:
        return self._song

    def candidates(self) -> list[SongCandidate]:
        return list(self._candidates)

    def candidate_buttons(self) -> list[PushButton]:
        return list(self._candidate_buttons)

    def status(self) -> str:
        return str(self.status_label.text())

    # -- writing -------------------------------------------------------------------------

    def set_text(self, text: str) -> None:
        self.input.setPlainText(text)

    def set_hint(self, text: str) -> None:
        self.hint_label.setText(text)
        self.hint_label.setVisible(bool(text))

    def set_busy(self, busy: bool) -> None:
        self.setEnabled(not busy)

    def set_status(self, text: str, level: StatusLevel = "info") -> None:
        self.status_label.setText(text)
        colors = _DARK_COLORS if isDarkTheme() else _COLORS
        self.status_label.setStyleSheet(f"color: {colors[level]};")

    def set_song(self, song: Song | None, status: str | None = None) -> None:
        """Show ``song`` as the card's song (``None`` = no song) and clear the candidates."""
        self._song = song
        self._set_candidates([])
        self.edit_button.setEnabled(song is not None)
        if song is None:
            self.set_status("Sem canto", "info")
        else:
            self.set_status(status or f"«{song.title}»", "ok")

    def set_result(self, result: MomentResult) -> None:
        """Apply the outcome of resolving this card's text."""
        self._song = result.song
        self.edit_button.setEnabled(result.song is not None)
        self._set_candidates(result.candidates if result.song is None else [])
        errors = [n.message for n in result.notices if n.level == "error"]
        warnings = [n.message for n in result.notices if n.level != "error"]
        if result.song is not None:
            origin = _ORIGINS.get(result.origin, "Encontrado")
            extra = f" — {warnings[0]}" if warnings else ""
            level: StatusLevel = "warning" if warnings else "ok"
            self.set_status(f"{origin}: «{result.song.title}»{extra}", level)
        elif result.candidates:
            self.set_status("Encontrei estas possibilidades: escolha uma.", "warning")
        elif errors:
            self.set_status(f"Aviso: {errors[0]}", "error")
        elif warnings:
            self.set_status(f"Aviso: {warnings[0]}", "warning")
        else:
            self.set_status("Nada encontrado. Informe o link ou cole a letra.", "warning")

    def clear(self) -> None:
        self.input.clear()
        self.set_song(None)

    # -- internals -----------------------------------------------------------------------

    def _set_candidates(self, candidates: list[SongCandidate]) -> None:
        for button in self._candidate_buttons:
            button.deleteLater()
        self._candidate_buttons = []
        self._candidates = list(candidates)
        for candidate in candidates:
            artist = f" — {candidate.artist}" if candidate.artist else ""
            origin = " (banco)" if candidate.song_id is not None else " (internet)"
            button = PushButton(f"Usar: {candidate.title}{artist}{origin}")
            button.clicked.connect(lambda _checked=False, c=candidate: self._emit_choice(c))
            self._candidates_box.addWidget(button)
            self._candidate_buttons.append(button)

    def _emit_choice(self, candidate: SongCandidate) -> None:
        self.candidate_chosen.emit(self.moment, candidate)

    def _emit_resolve(self) -> None:
        if self.text():
            self.resolve_requested.emit(self.moment, self.text())
        else:
            self.set_status("Digite um título, um link ou cole a letra.", "warning")

    def _emit_clear(self) -> None:
        self.clear()
        self.clear_requested.emit(self.moment)
