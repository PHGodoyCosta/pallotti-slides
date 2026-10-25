"""Confirmation screen for automatic moment assignments (SPEC F4, ARQUITETURA §11).

Used for repertoire links and for free text: nothing is applied until the user confirms.
"""

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    PrimaryPushButton,
    PushButton,
    SmoothScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
)

from pallotti_slides.application.new_mass import ProposedSong
from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import SongRequest

Confidence = Literal["high", "low", "none"]

IGNORE = "Ignorar este canto"
_WARNING_COLOR = "#B25E00"
_ERROR_COLOR = "#C42B1C"


@dataclass(frozen=True)
class ConfirmItem:
    """A song with the moment we suggest. ``text`` is what goes into the card on confirm."""

    title: str
    text: str
    moment: SongMoment | None
    artist: str | None = None
    confidence: Confidence = "high"
    reason: str = ""
    source: str = ""

    @classmethod
    def from_proposed(cls, proposed: ProposedSong) -> "ConfirmItem":
        return cls(
            title=proposed.title,
            text=proposed.url,
            moment=proposed.moment,
            artist=proposed.artist,
            confidence=proposed.confidence,
            reason=proposed.reason,
            source="repertório",
        )

    @classmethod
    def from_request(cls, request: SongRequest) -> "ConfirmItem":
        first = next((line.strip() for line in request.text.splitlines() if line.strip()), "")
        return cls(
            title=first[:80] or "(sem título)",
            text=request.text,
            moment=request.moment,
            reason="reconhecido no texto livre",
            source="texto livre",
        )


class _ItemRow(CardWidget):  # type: ignore[misc]
    changed = Signal()

    def __init__(self, item: ConfirmItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        self.combo = ComboBox()
        self.combo.addItem(IGNORE, userData=None)
        for moment in SongMoment:
            self.combo.addItem(moment.label, userData=moment)
        index = 0 if item.moment is None else list(SongMoment).index(item.moment) + 1
        self.combo.setCurrentIndex(index)
        self.combo.setMinimumWidth(190)
        self.combo.currentIndexChanged.connect(lambda _i: self.changed.emit())

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(StrongBodyLabel(item.title))
        details = " · ".join(part for part in (item.artist, item.source) if part)
        if item.reason:
            details += f" — sugestão: {item.reason}" if details else f"Sugestão: {item.reason}"
        if details:
            text.addWidget(CaptionLabel(details))
        self.low_label = CaptionLabel("Confiança baixa: confira o momento deste canto.")
        self.low_label.setStyleSheet(f"color: {_WARNING_COLOR};")
        self.low_label.setVisible(item.confidence == "low")
        text.addWidget(self.low_label)
        self.replace_label = CaptionLabel("Vai substituir o canto que já está neste momento.")
        self.replace_label.setStyleSheet(f"color: {_WARNING_COLOR};")
        self.replace_label.hide()
        text.addWidget(self.replace_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)
        layout.addLayout(text, 1)
        layout.addWidget(self.combo)
        if item.confidence == "low":
            self.setStyleSheet("CardWidget { border: 1px solid " + _WARNING_COLOR + "; }")

    def moment(self) -> SongMoment | None:
        data = self.combo.currentData()
        return data if isinstance(data, SongMoment) else None


class RepertoireConfirm(QWidget):
    """ "Estes são os cantos que encontrei": one moment selector per song."""

    confirmed = Signal(object)  # dict[SongMoment, ConfirmItem]
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("repertoire-confirm")
        self._rows: list[_ItemRow] = []
        self._filled: set[SongMoment] = set()

        self.title_label = SubtitleLabel("Estes são os cantos que encontrei")
        self.intro_label = BodyLabel("")
        self.intro_label.setWordWrap(True)
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(8)
        self.missing_label = BodyLabel("")
        self.missing_label.setWordWrap(True)
        self.error_label = BodyLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f"color: {_ERROR_COLOR};")
        self.confirm_button = PrimaryPushButton("Confirmar e preencher os cantos")
        self.cancel_button = PushButton("Agora não")
        self.confirm_button.clicked.connect(self._confirm)
        self.cancel_button.clicked.connect(self.cancelled)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 12, 0)
        body_layout.addLayout(self.items_layout)
        body_layout.addStretch(1)
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidget(body)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        body.setStyleSheet("background: transparent;")

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.confirm_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.intro_label)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(self.missing_label)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

    def set_items(self, items: list[ConfirmItem], filled: set[SongMoment] | None = None) -> None:
        """Show ``items``; ``filled`` are the moments whose card already has a song."""
        for row in self._rows:
            row.deleteLater()
        self._rows = []
        self._filled = set(filled or ())
        for item in items:
            row = _ItemRow(item)
            row.changed.connect(self._refresh)
            self.items_layout.addWidget(row)
            self._rows.append(row)
        self.intro_label.setText(
            f"Encontrei {len(items)} canto(s). A ordem pode estar errada ou haver cantos a mais: "
            "troque o momento, escolha «Ignorar» e depois complete os que faltam. "
            "Nada é preenchido antes de você confirmar."
        )
        self._refresh()

    def rows(self) -> list[_ItemRow]:
        return list(self._rows)

    def assignments(self) -> dict[SongMoment, ConfirmItem]:
        """The current choice per moment (ignored songs left out)."""
        result: dict[SongMoment, ConfirmItem] = {}
        for row in self._rows:
            moment = row.moment()
            if moment is not None:
                result[moment] = row.item
        return result

    def missing_moments(self) -> list[SongMoment]:
        """Moments with no song, neither proposed here nor already in a card."""
        taken = {m for row in self._rows if (m := row.moment()) is not None} | self._filled
        return [moment for moment in SongMoment if moment not in taken]

    def conflicts(self) -> list[SongMoment]:
        """Moments chosen for more than one song."""
        seen: set[SongMoment] = set()
        repeated: list[SongMoment] = []
        for row in self._rows:
            moment = row.moment()
            if moment is None:
                continue
            if moment in seen and moment not in repeated:
                repeated.append(moment)
            seen.add(moment)
        return repeated

    def _refresh(self) -> None:
        for row in self._rows:
            moment = row.moment()
            row.replace_label.setVisible(moment is not None and moment in self._filled)
        missing = self.missing_moments()
        if missing:
            names = ", ".join(moment.label for moment in missing)
            self.missing_label.setText(f"Momentos sem canto (você completa depois): {names}.")
        else:
            self.missing_label.setText("Todos os momentos têm canto.")
        repeated = self.conflicts()
        if repeated:
            names = ", ".join(moment.label for moment in repeated)
            self.error_label.setText(f"Mais de um canto em: {names}. Troque ou ignore um deles.")
        else:
            self.error_label.setText("")
        self.error_label.setVisible(bool(repeated))
        self.confirm_button.setEnabled(not repeated)

    def _confirm(self) -> None:
        if not self.conflicts():
            self.confirmed.emit(self.assignments())
