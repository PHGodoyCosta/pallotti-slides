"""History page (SPEC F13): saved Masses with open-folder, reopen and duplicate."""

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    InfoBar,
    PushButton,
    ScrollArea,
    StrongBodyLabel,
    TitleLabel,
)

from pallotti_slides.application.mass_history import MassHistory, MassSummary
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Mass


def format_files(summary: MassSummary) -> str:
    """Short text with the generated files (name only)."""
    names = [p.name for p in (summary.pptx_path, summary.pdf_path) if p is not None]
    return " · ".join(names) if names else "Sem arquivos gerados"


class _MassRow(CardWidget):  # type: ignore[misc]
    def __init__(self, summary: MassSummary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.summary = summary
        title = StrongBodyLabel(summary.title)
        info = BodyLabel(
            f"{summary.date.strftime('%d/%m/%Y')} · Oração Eucarística "
            f"{summary.eucharistic_prayer.label}"
        )
        self.files_label = CaptionLabel(format_files(summary))
        self.open_button = PushButton(FluentIcon.FOLDER, "Abrir pasta")
        self.reopen_button = PushButton(FluentIcon.EDIT, "Reabrir")
        self.duplicate_button = PushButton(FluentIcon.COPY, "Duplicar")
        self.open_button.setEnabled(self.folder() is not None)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(title)
        text.addWidget(info)
        text.addWidget(self.files_label)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.addLayout(text, 1)
        for button in (self.open_button, self.reopen_button, self.duplicate_button):
            layout.addWidget(button)

    def folder(self) -> Path | None:
        for path in (self.summary.pptx_path, self.summary.pdf_path):
            if path is not None:
                return path.parent
        return None


class HistoryPage(QWidget):
    """List of Masses from the repository, newest first."""

    mass_requested = Signal(object, bool)  # (Mass, duplicate)

    def __init__(self, repo: MassHistory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("history-page")
        self._repo = repo
        self.rows: list[_MassRow] = []
        self.empty_label = BodyLabel("Nenhuma missa gerada ainda.")

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(10)
        content = QWidget()
        content.setObjectName("history-content")
        content.setStyleSheet("#history-content{background:transparent}")
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 8, 12, 24)
        column.addWidget(self.empty_label)
        column.addLayout(self._rows_layout)
        column.addStretch(1)
        scroll = ScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(ScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("ScrollArea{background:transparent;border:none}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 28, 24, 0)
        outer.addWidget(TitleLabel("Histórico"))
        outer.addWidget(scroll, 1)
        self.refresh()

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """Reload the list from the repository."""
        for row in self.rows:
            self._rows_layout.removeWidget(row)
            row.deleteLater()
        self.rows = []
        for summary in self._repo.list():
            row = _MassRow(summary)
            row.open_button.clicked.connect(lambda _c=False, r=row: self._open_folder(r))
            row.reopen_button.clicked.connect(lambda _c=False, r=row: self._request(r, False))
            row.duplicate_button.clicked.connect(lambda _c=False, r=row: self._request(r, True))
            self._rows_layout.addWidget(row)
            self.rows.append(row)
        self.empty_label.setVisible(not self.rows)

    def _open_folder(self, row: _MassRow) -> None:
        folder = row.folder()
        if folder is None or not folder.is_dir():
            InfoBar.warning("Histórico", "A pasta não existe mais.", parent=self.window())
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _request(self, row: _MassRow, duplicate: bool) -> None:
        try:
            mass: Mass = self._repo.get(row.summary.id)
        except PallottiError as error:
            InfoBar.error("Histórico", str(error), parent=self.window())
            return
        self.mass_requested.emit(mass, duplicate)
