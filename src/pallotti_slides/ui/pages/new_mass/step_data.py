"""Step 1 — Dados: date, leaflet PDF, free text and repertoire link (SPEC F1)."""

import datetime as dt
from pathlib import Path

from PySide6.QtCore import QDate, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CalendarPicker,
    CaptionLabel,
    FluentIcon,
    LineEdit,
    PlainTextEdit,
    PushButton,
    StrongBodyLabel,
)

_ERROR_COLOR = "#C42B1C"
MIN_YEAR, MAX_YEAR = 2000, 2100


class LeafletDropZone(QFrame):
    """Drop area for the leaflet PDF, with a file chooser button."""

    file_chosen = Signal(object)  # Path | None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("leaflet-drop-zone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(88)
        self.setStyleSheet("#leaflet-drop-zone { border: 2px dashed #9A9A9A; border-radius: 8px; }")
        self._path: Path | None = None
        self.label = BodyLabel("Arraste o folheto (PDF) para cá ou")
        self.name_label = StrongBodyLabel("")
        self.name_label.hide()
        self.error_label = CaptionLabel("")
        self.error_label.setStyleSheet(f"color: {_ERROR_COLOR};")
        self.error_label.hide()
        self.choose_button = PushButton(FluentIcon.FOLDER, "Escolher PDF…")
        self.remove_button = PushButton(FluentIcon.CLOSE, "Remover")
        self.remove_button.hide()
        self.choose_button.clicked.connect(self._choose)
        self.remove_button.clicked.connect(lambda: self.set_path(None, emit=True))

        buttons = QHBoxLayout()
        buttons.addWidget(self.choose_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        layout.addWidget(self.label)
        layout.addWidget(self.name_label)
        layout.addLayout(buttons)
        layout.addWidget(self.error_label)

    def path(self) -> Path | None:
        return self._path

    def set_path(self, path: Path | None, *, emit: bool = False) -> bool:
        """Accept ``path`` if it is a PDF (``None`` clears). Returns whether it was accepted."""
        if path is not None and path.suffix.lower() != ".pdf":
            self.error_label.setText(f"«{path.name}» não é um PDF. Escolha o folheto em PDF.")
            self.error_label.show()
            return False
        self.error_label.hide()
        self._path = path
        self.name_label.setText(path.name if path else "")
        self.name_label.setVisible(path is not None)
        self.remove_button.setVisible(path is not None)
        self.label.setText(
            "Folheto escolhido (o PDF é lido só quando você avançar):"
            if path
            else "Arraste o folheto (PDF) para cá ou"
        )
        if emit:
            self.file_chosen.emit(path)
        return True

    def _choose(self) -> None:
        name, _ = QFileDialog.getOpenFileName(
            self, "Escolher o folheto", str(Path.home()), "Folheto (*.pdf)"
        )
        if name:
            self.set_path(Path(name), emit=True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if urls and self.set_path(Path(urls[0]), emit=True):
            event.acceptProposedAction()


class StepData(QWidget):
    """Date, leaflet, free text and repertoire link."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step-data")
        self.date_picker = CalendarPicker()
        self.date_picker.setDateFormat("dd/MM/yyyy")
        self.date_picker.setMinimumWidth(180)
        self.date_error = BodyLabel("")
        self.date_error.setStyleSheet(f"color: {_ERROR_COLOR};")
        self.date_error.hide()
        self.drop_zone = LeafletDropZone()
        self.free_text = PlainTextEdit()
        self.free_text.setPlaceholderText(
            "Opcional. Ex.: Entrada: Me chamaste; Ofertório: https://…; Comunhão: Pão da vida"
        )
        self.free_text.setFixedHeight(90)
        self.repertoire_edit = LineEdit()
        self.repertoire_edit.setPlaceholderText("Opcional. Ex.: link de repertório do Cifra Club")
        self.repertoire_edit.setClearButtonEnabled(True)
        self.date_picker.dateChanged.connect(lambda _d: self.date_error.hide())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(StrongBodyLabel("Data da celebração"))
        row = QHBoxLayout()
        row.addWidget(self.date_picker)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(self.date_error)
        layout.addSpacing(6)
        layout.addWidget(StrongBodyLabel("Folheto litúrgico (opcional)"))
        layout.addWidget(self.drop_zone)
        layout.addSpacing(6)
        layout.addWidget(StrongBodyLabel("Cantos em texto livre (opcional)"))
        layout.addWidget(self.free_text)
        layout.addSpacing(6)
        layout.addWidget(StrongBodyLabel("Link de repertório (opcional)"))
        layout.addWidget(self.repertoire_edit)
        layout.addWidget(
            CaptionLabel(
                "Os cantos do texto livre e do link só entram na missa depois que você "
                "confirmar o momento de cada um, na etapa Cantos."
            )
        )
        layout.addStretch(1)

    def date(self) -> dt.date | None:
        """The chosen date, or ``None`` when empty or out of range."""
        picked: QDate = self.date_picker.getDate()
        if not picked.isValid() or not MIN_YEAR <= picked.year() <= MAX_YEAR:
            return None
        return dt.date(picked.year(), picked.month(), picked.day())

    def set_date(self, value: dt.date | None) -> None:
        if value is None:
            self.date_picker.reset()
        else:
            self.date_picker.setDate(QDate(value.year, value.month, value.day))
        self.date_error.hide()

    def validate_date(self) -> bool:
        """``False`` (with a visible message) when the date is missing or invalid."""
        if self.date() is not None:
            self.date_error.hide()
            return True
        self.date_error.setText(
            "Data inválida ou não informada. Escolha a data da celebração no calendário."
        )
        self.date_error.show()
        return False

    def leaflet_path(self) -> Path | None:
        return self.drop_zone.path()

    def free_text_value(self) -> str:
        return str(self.free_text.toPlainText()).strip()

    def repertoire_url(self) -> str:
        return str(self.repertoire_edit.text()).strip()

    def set_busy(self, busy: bool) -> None:
        self.setEnabled(not busy)
