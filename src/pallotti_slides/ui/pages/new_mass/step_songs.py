"""Step 3 — Cantos: one card per moment, plus the confirmation screen (SPEC F4, F5)."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import SmoothScrollArea

from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import Song
from pallotti_slides.ui.components.moment_card import MomentCard
from pallotti_slides.ui.components.repertoire_confirm import ConfirmItem, RepertoireConfirm


class StepSongs(QWidget):
    """Cards for the nine moments; a pending proposal replaces them until it is answered."""

    resolve_requested = Signal(object, str)
    candidate_chosen = Signal(object, object)
    edit_requested = Signal(object)
    clear_requested = Signal(object)
    assignments_confirmed = Signal(object)  # dict[SongMoment, ConfirmItem]
    confirmation_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step-songs")
        self.cards: dict[SongMoment, MomentCard] = {}
        self._pending: list[ConfirmItem] = []

        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 12, 0)
        column.setSpacing(10)
        for moment in SongMoment:
            card = MomentCard(moment)
            card.resolve_requested.connect(self.resolve_requested)
            card.candidate_chosen.connect(self.candidate_chosen)
            card.edit_requested.connect(self.edit_requested)
            card.clear_requested.connect(self.clear_requested)
            self.cards[moment] = card
            column.addWidget(card)
        column.addStretch(1)
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidget(body)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        body.setStyleSheet("background: transparent;")

        self.confirm = RepertoireConfirm()
        self.confirm.confirmed.connect(self._on_confirmed)
        self.confirm.cancelled.connect(self._on_cancelled)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.scroll_area)
        self.stack.addWidget(self.confirm)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

    # -- reading -------------------------------------------------------------------------

    def songs(self) -> dict[SongMoment, Song]:
        return {m: song for m, card in self.cards.items() if (song := card.song()) is not None}

    def filled_moments(self) -> set[SongMoment]:
        """Moments whose card has a song or typed text."""
        return {m for m, card in self.cards.items() if card.song() or card.text()}

    def is_confirming(self) -> bool:
        return self.stack.currentWidget() is self.confirm

    def has_pending_confirmation(self) -> bool:
        return bool(self._pending)

    def unresolved(self) -> dict[SongMoment, str]:
        """Typed text with no song yet (or with candidates still waiting)."""
        return {m: c.text() for m, c in self.cards.items() if c.text() and c.song() is None}

    # -- confirmation --------------------------------------------------------------------

    def set_pending_confirmation(self, items: list[ConfirmItem]) -> None:
        """Replace the proposals waiting for an answer (shown by ``show_pending_confirmation``)."""
        self._pending = list(items)

    def show_pending_confirmation(self) -> bool:
        """Show the confirmation screen when there is something to confirm."""
        if not self._pending:
            return False
        self.confirm.set_items(list(self._pending), self.filled_moments())
        self.stack.setCurrentWidget(self.confirm)
        return True

    def _finish_confirmation(self) -> None:
        self._pending = []
        self.stack.setCurrentWidget(self.scroll_area)

    def _on_confirmed(self, assignments: object) -> None:
        self._finish_confirmation()
        self.assignments_confirmed.emit(assignments)

    def _on_cancelled(self) -> None:
        self._finish_confirmation()
        self.confirmation_cancelled.emit()

    # -- misc ----------------------------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        self.setEnabled(not busy)

    def set_gloria_enabled(self, enabled: bool) -> None:
        card = self.cards[SongMoment.GLORIA]
        card.set_hint(
            "" if enabled else "Esta missa está sem Glória: o canto deste cartão será ignorado."
        )

    def clear_all(self) -> None:
        for card in self.cards.values():
            card.clear()
        self._pending = []
        self.stack.setCurrentWidget(self.scroll_area)
