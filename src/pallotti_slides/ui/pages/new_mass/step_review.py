"""Step 4 — Revisão: notices, slide thumbnails and the Generate button (SPEC F7)."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    InfoBar,
    InfoBarIcon,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
)

from pallotti_slides.domain.models import Notice
from pallotti_slides.ui.components.slides_preview import SlidesPreview

_LEVEL_TITLE = {"error": "Erro", "warning": "Atenção", "info": "Informação"}
_LEVEL_ICON = {
    "error": InfoBarIcon.ERROR,
    "warning": InfoBarIcon.WARNING,
    "info": InfoBarIcon.INFORMATION,
}


class StepReview(QWidget):
    """Shows what blocks or worries, the result of the generation and a slide preview."""

    generate_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step-review")
        self._output_dir = Path.home()
        self._blocked = False
        self._busy = False
        self._folder_to_open: Path | None = None

        self.summary_label = BodyLabel("")
        self.summary_label.setWordWrap(True)
        self.notices_box = QVBoxLayout()
        self.notices_box.setSpacing(6)
        self._bars: list[InfoBar] = []

        self.folder_label = CaptionLabel("")
        self.folder_label.setWordWrap(True)
        self.folder_button = PushButton(FluentIcon.FOLDER, "Mudar pasta…")
        self.folder_button.clicked.connect(self._choose_folder)
        self.generate_button = PrimaryPushButton(FluentIcon.PLAY, "Gerar")
        self.generate_button.clicked.connect(self.generate_requested)

        self.result_title = StrongBodyLabel("Missa gerada")
        self.pptx_label = BodyLabel("")
        self.pdf_label = BodyLabel("")
        for label in (self.pptx_label, self.pdf_label):
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.open_button = PushButton(FluentIcon.FOLDER, "Abrir pasta")
        self.open_button.clicked.connect(self.open_folder)
        self.result_widgets = [self.result_title, self.pptx_label, self.pdf_label, self.open_button]
        for widget in self.result_widgets:
            widget.hide()

        self.preview = SlidesPreview()

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self.generate_button)
        actions.addWidget(self.folder_button)
        actions.addWidget(self.folder_label, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.summary_label)
        layout.addLayout(self.notices_box)
        layout.addLayout(actions)
        result_text = QVBoxLayout()
        result_text.setSpacing(2)
        result_text.addWidget(self.result_title)
        result_text.addWidget(self.pptx_label)
        result_text.addWidget(self.pdf_label)
        result = QHBoxLayout()
        result.setSpacing(12)
        result.addLayout(result_text, 1)
        result.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(result)
        layout.addWidget(self.preview, 1)
        self.set_output_dir(self._output_dir)

    # -- state ---------------------------------------------------------------------------

    def set_summary(self, text: str) -> None:
        self.summary_label.setText(text)

    def set_output_dir(self, folder: Path) -> None:
        self._output_dir = folder
        self.folder_label.setText(f"Salvar em: {folder}")

    def output_dir(self) -> Path:
        return self._output_dir

    def set_notices(self, notices: list[Notice]) -> None:
        """Show ``notices`` as InfoBars; an error blocks the Generate button."""
        for bar in self._bars:
            bar.deleteLater()
        self._bars = []
        order = {"error": 0, "warning": 1, "info": 2}
        for notice in sorted(notices, key=lambda n: order[n.level]):
            bar = InfoBar(
                _LEVEL_ICON[notice.level],
                _LEVEL_TITLE[notice.level],
                notice.message,
                orient=Qt.Orientation.Horizontal,
                isClosable=False,
                duration=-1,
                position=InfoBarPosition.NONE,
                parent=self,
            )
            bar.setProperty("level", notice.level)
            self.notices_box.addWidget(bar)
            bar.show()
            self._bars.append(bar)
        self._blocked = any(n.level == "error" for n in notices)
        self._update_button()

    def notice_messages(self) -> list[tuple[str, str]]:
        """``(level, message)`` of the bars shown."""
        return [(str(bar.property("level")), str(bar.content)) for bar in self._bars]

    def is_blocked(self) -> bool:
        return self._blocked

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_button()

    def _update_button(self) -> None:
        self.generate_button.setEnabled(not self._blocked and not self._busy)
        self.generate_button.setToolTip(
            "Corrija os erros acima para poder gerar." if self._blocked else ""
        )

    # -- result --------------------------------------------------------------------------

    def show_result(self, pptx: Path, pdf: Path | None) -> None:
        self._folder_to_open = pptx.parent
        self.pptx_label.setText(f"PowerPoint: {pptx}")
        self.pdf_label.setText(f"PDF: {pdf}" if pdf else "PDF: não foi gerado (veja os avisos).")
        for widget in self.result_widgets:
            widget.show()
        if pdf is not None:
            self.preview.set_pdf(pdf)
        else:
            self.preview.clear()

    def hide_result(self) -> None:
        for widget in self.result_widgets:
            widget.hide()
        self.preview.clear()
        self._folder_to_open = None

    def result_visible(self) -> bool:
        return not self.pptx_label.isHidden()

    def open_folder(self) -> None:
        if self._folder_to_open is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._folder_to_open)))

    def _choose_folder(self) -> None:
        name = QFileDialog.getExistingDirectory(
            self, "Pasta para salvar a missa", str(self._output_dir)
        )
        if name:
            self.set_output_dir(Path(name))
