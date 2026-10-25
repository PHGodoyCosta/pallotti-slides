"""About page: name, version, license, credits."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, SubtitleLabel, TitleLabel

from pallotti_slides import __version__
from pallotti_slides.ui.assets import load_pixmap

ABOUT_IMAGE = "pallotti1.webp"
LICENSE_NAME = "GNU GPL v3"


class AboutPage(QWidget):
    """Program identity and credits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("about-page")

        text = QVBoxLayout()
        text.setSpacing(10)
        text.addStretch(1)
        text.addWidget(TitleLabel("Pallotti Slides"))
        self.version_label = SubtitleLabel(f"Versão {__version__}")
        text.addWidget(self.version_label)
        text.addWidget(
            BodyLabel("Gerador dos slides da missa de domingo da Paróquia São Cristóvão.")
        )
        text.addWidget(BodyLabel(f"Licença: {LICENSE_NAME}"))
        text.addSpacing(10)
        credits_title = SubtitleLabel("Créditos")
        text.addWidget(credits_title)
        credits_text = BodyLabel(
            "Tema visual: São Vicente Pallotti, fundador da Sociedade do Apostolado Católico.\n"
            "Interface: PySide6 e QFluentWidgets.\n"
            "Letras e orações são de responsabilidade de quem as fornece; "
            "a IA apenas extrai e classifica."
        )
        credits_text.setWordWrap(True)
        text.addWidget(credits_text)
        text.addWidget(
            CaptionLabel("A fonte Aptos pertence à Microsoft e não é distribuída com o programa.")
        )
        text.addStretch(2)

        picture = QLabel()
        picture.setPixmap(load_pixmap(ABOUT_IMAGE, height=420))
        picture.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setSpacing(48)
        layout.addLayout(text, 3)
        layout.addWidget(picture, 2)
