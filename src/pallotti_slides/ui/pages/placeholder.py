"""Simple "under construction" page for sections that are not built yet."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, TitleLabel


class PlaceholderPage(QWidget):
    """Title plus "Em construção"."""

    def __init__(self, title: str, object_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.addWidget(TitleLabel(title))
        layout.addWidget(BodyLabel("Em construção"))
        layout.addStretch(1)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
