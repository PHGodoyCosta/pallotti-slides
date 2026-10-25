"""Thumbnails of the generated PDF (QtPdf), rendered a few at a time to keep the UI alive."""

from pathlib import Path

from PySide6.QtCore import QSize, QSizeF, Qt, QTimer
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, SmoothScrollArea

THUMB_WIDTH = 200
THUMB_HEIGHT = 113  # 16:9 slides
PAGES_PER_TICK = 4


class SlidesPreview(QWidget):
    """Grid of slide thumbnails of a PDF."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("slides-preview")
        self._document = QPdfDocument(self)
        self._next_page = 0
        self._labels: list[QLabel] = []
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._render_some)

        body = QWidget()
        self._columns = 1
        self._grid = QGridLayout(body)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(10)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.setStyleSheet("background: transparent;")
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidget(body)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.scroll_area.setMinimumHeight(170)
        self.caption = CaptionLabel("A pré-visualização aparece depois de gerar.")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.caption)
        layout.addWidget(self.scroll_area, 1)

    def set_pdf(self, pdf: Path) -> bool:
        """Load ``pdf`` and start drawing its thumbnails; ``False`` if it cannot be read."""
        self.clear()
        error = self._document.load(str(pdf))
        if error != QPdfDocument.Error.None_ or self._document.pageCount() == 0:
            self.caption.setText("Não consegui abrir o PDF para a pré-visualização.")
            return False
        total = self._document.pageCount()
        self.caption.setText(f"{total} slide(s)")
        for index in range(total):
            label = QLabel(f"{index + 1}")
            label.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background: #DDDDDD; border: 1px solid #BBBBBB;")
            self._labels.append(label)
        self._relayout()
        self._timer.start()
        return True

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        """Thumbnails flow into as many columns as fit the width."""
        width = self.scroll_area.viewport().width()
        columns = max(1, (width + 10) // (THUMB_WIDTH + 10))
        if columns == self._columns and self._grid.count() == len(self._labels):
            return
        self._columns = columns
        for label in self._labels:
            self._grid.removeWidget(label)
        for index, label in enumerate(self._labels):
            self._grid.addWidget(label, index // columns, index % columns)

    def clear(self) -> None:
        self._timer.stop()
        self._next_page = 0
        for label in self._labels:
            label.deleteLater()
        self._labels = []
        self._document.close()
        self.caption.setText("A pré-visualização aparece depois de gerar.")

    def page_count(self) -> int:
        """Number of thumbnails (placeholders included)."""
        return len(self._labels)

    def rendered_count(self) -> int:
        """Thumbnails already drawn."""
        return self._next_page

    def render_all(self) -> None:
        """Draw every remaining thumbnail now (tests and screenshots)."""
        while self._next_page < len(self._labels):
            self._render_some()

    def _render_some(self) -> None:
        for _ in range(PAGES_PER_TICK):
            if self._next_page >= len(self._labels):
                self._timer.stop()
                return
            index = self._next_page
            self._next_page += 1
            page: QSizeF = self._document.pagePointSize(index)
            size = page.scaled(
                QSizeF(THUMB_WIDTH, THUMB_HEIGHT), Qt.AspectRatioMode.KeepAspectRatio
            ).toSize()
            image = self._document.render(index, QSize(size))
            label = self._labels[index]
            label.setStyleSheet("border: 1px solid #BBBBBB;")
            label.setPixmap(QPixmap.fromImage(image))
