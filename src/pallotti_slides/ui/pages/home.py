"""Home page: welcome, Pallotti's picture and shortcuts."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    TitleLabel,
)

from pallotti_slides.ui.assets import load_pixmap

HOME_IMAGE = "pallotti2.jpg"


class HomePage(QWidget):
    """Welcome screen with two shortcuts (signals; the window does the navigation)."""

    new_mass_requested = Signal()
    history_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("home-page")

        text = QVBoxLayout()
        text.setSpacing(12)
        text.addStretch(1)
        text.addWidget(TitleLabel("Pallotti Slides"))
        text.addWidget(SubtitleLabel("Paróquia São Cristóvão"))
        intro = BodyLabel(
            "Gere os slides da missa de domingo a partir do folheto litúrgico e dos cantos. "
            "Revise tudo antes de exportar o PowerPoint e o PDF."
        )
        intro.setWordWrap(True)
        text.addWidget(intro)
        text.addSpacing(12)

        self.new_mass_button = PrimaryPushButton(FluentIcon.ADD, "Nova missa")
        self.history_button = PushButton(FluentIcon.HISTORY, "Abrir histórico")
        self.new_mass_button.clicked.connect(self.new_mass_requested)
        self.history_button.clicked.connect(self.history_requested)
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addWidget(self.new_mass_button)
        buttons.addWidget(self.history_button)
        buttons.addStretch(1)
        text.addLayout(buttons)
        text.addStretch(2)

        picture = QLabel()
        picture.setPixmap(load_pixmap(HOME_IMAGE, height=420))
        picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption = BodyLabel("São Vicente Pallotti")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side = QVBoxLayout()
        side.addStretch(1)
        side.addWidget(picture)
        side.addWidget(caption)
        side.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setSpacing(48)
        layout.addLayout(text, 3)
        layout.addLayout(side, 2)
