"""Settings page (SPEC F14): AI provider and keys, paths, typography, theme and diagnostic."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIntValidator
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ColorPickerButton,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
    TitleLabel,
)

from pallotti_slides.application.settings_service import (
    PROVIDER_NAMES,
    PROVIDERS,
    DiagnosticItem,
    SettingsService,
)
from pallotti_slides.config import Settings, TypographyConfig
from pallotti_slides.ui.theme import apply_theme

_THEME_LABELS = {"system": "Seguir o sistema", "light": "Claro", "dark": "Escuro"}


class _PathField(QWidget):
    """Line edit plus a button that opens a file or folder dialog."""

    def __init__(self, *, folder: bool, filter_: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folder = folder
        self._filter = filter_
        self.edit = LineEdit()
        self.button = PushButton("Escolher…")
        self.button.clicked.connect(self._choose)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    def _choose(self) -> None:
        if self._folder:
            chosen = QFileDialog.getExistingDirectory(self, "Escolher pasta", self.edit.text())
        else:
            chosen, _ = QFileDialog.getOpenFileName(
                self, "Escolher arquivo", self.edit.text(), self._filter
            )
        if chosen:
            self.edit.setText(chosen)

    def path(self) -> Path | None:
        text = self.edit.text().strip()
        return Path(text) if text else None

    def set_path(self, path: Path | None) -> None:
        self.edit.setText(str(path) if path else "")


class _IntField(LineEdit):  # type: ignore[misc]
    """Small integer input (the Fluent spin box clips its text on some styles)."""

    def setRange(self, low: int, high: int) -> None:
        self.setValidator(QIntValidator(low, high, self))
        self._low = low

    def value(self) -> int:
        try:
            return int(self.text())
        except ValueError:
            return getattr(self, "_low", 0)

    def setValue(self, value: int) -> None:
        self.setText(str(value))


class _KeyRow(QWidget):
    """Masked key field for one provider with Save/Remove; only shows "configurada"."""

    changed = Signal()

    def __init__(self, provider: str, service: SettingsService, parent: QWidget | None = None):
        super().__init__(parent)
        self.provider = provider
        self._service = service
        self.field = PasswordLineEdit()
        self.field.setPlaceholderText("Cole a chave da API")
        self.status = CaptionLabel()
        self.save_button = PushButton("Salvar chave")
        self.remove_button = PushButton("Remover")
        self.save_button.clicked.connect(self._save)
        self.remove_button.clicked.connect(self._remove)
        row = QHBoxLayout()
        row.addWidget(self.field, 1)
        row.addWidget(self.save_button)
        row.addWidget(self.remove_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(row)
        layout.addWidget(self.status)
        self.refresh()

    def refresh(self) -> None:
        configured = self._service.has_key(self.provider)
        self.status.setText("Chave: configurada" if configured else "Chave: não configurada")
        self.remove_button.setEnabled(configured)

    def _save(self) -> None:
        from pallotti_slides.domain.errors import PallottiError

        try:
            self._service.save_key(self.provider, self.field.text())
        except PallottiError as error:
            InfoBar.error("Chave", str(error), parent=self.window(), duration=5000)
            return
        self.field.clear()  # the value never stays on screen
        self.refresh()
        self.changed.emit()

    def _remove(self) -> None:
        self._service.remove_key(self.provider)
        self.field.clear()
        self.refresh()
        self.changed.emit()


class SettingsPage(QWidget):
    """Edit and persist ``Settings``; theme applies immediately."""

    settings_saved = Signal(object)

    def __init__(self, service: SettingsService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settings-page")
        self._service = service
        self.settings = service.load()

        self.provider_combo = ComboBox()
        for provider in PROVIDERS:
            self.provider_combo.addItem(PROVIDER_NAMES[provider], userData=provider)
        self.openai_model = LineEdit()
        self.anthropic_model = LineEdit()
        self.openai_key = _KeyRow("openai", service)
        self.anthropic_key = _KeyRow("anthropic", service)
        self.output_dir = _PathField(folder=True)
        self.soffice = _PathField(folder=False)
        self.template = _PathField(folder=False, filter_="PowerPoint (*.pptx)")
        self.fonts_dir = _PathField(folder=True)
        self.min_font = _IntField()
        self.max_font = _IntField()
        self.max_lines = _IntField()
        for box, low, high in ((self.min_font, 10, 200), (self.max_font, 10, 200)):
            box.setRange(low, high)
        self.max_lines.setRange(1, 30)
        for box in (self.min_font, self.max_font, self.max_lines):
            box.setFixedWidth(130)
        self.theme_combo = ComboBox()
        for mode, label in _THEME_LABELS.items():
            self.theme_combo.addItem(label, userData=mode)
        self.accent_button = ColorPickerButton(QColor("#7A1F2B"), "Cor de destaque")
        self.save_button = PrimaryPushButton("Salvar configurações")
        self.diagnostic_layout = QVBoxLayout()
        self.diagnostic_rows: list[tuple[DiagnosticItem, BodyLabel]] = []
        self.refresh_diagnostic_button = PushButton("Verificar de novo")

        self._build()
        self._fill(self.settings)
        self.save_button.clicked.connect(self.save)
        self.refresh_diagnostic_button.clicked.connect(self.refresh_diagnostic)
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        self.accent_button.colorChanged.connect(self._theme_changed)
        self.provider_combo.currentIndexChanged.connect(lambda _i: self.refresh_diagnostic())
        self.openai_key.changed.connect(self.refresh_diagnostic)
        self.anthropic_key.changed.connect(self.refresh_diagnostic)
        self.refresh_diagnostic()

    # ---- layout -------------------------------------------------------------------------

    def _card(self, title: str, form: QFormLayout) -> CardWidget:
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.addWidget(SubtitleLabel(title))
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(form)
        return card

    def _build(self) -> None:
        ai = QFormLayout()
        ai.addRow(BodyLabel("Provedor"), self.provider_combo)
        ai.addRow(BodyLabel("Modelo OpenAI"), self.openai_model)
        ai.addRow(BodyLabel("Chave OpenAI"), self.openai_key)
        ai.addRow(BodyLabel("Modelo Anthropic"), self.anthropic_model)
        ai.addRow(BodyLabel("Chave Anthropic"), self.anthropic_key)

        paths = QFormLayout()
        paths.addRow(BodyLabel("Pasta de saída"), self.output_dir)
        paths.addRow(BodyLabel("LibreOffice (soffice)"), self.soffice)
        paths.addRow(BodyLabel("Modelo .pptx"), self.template)
        paths.addRow(BodyLabel("Pasta das fontes"), self.fonts_dir)

        typo = QFormLayout()
        typo.addRow(BodyLabel("Fonte mínima"), self.min_font)
        typo.addRow(BodyLabel("Fonte máxima"), self.max_font)
        typo.addRow(BodyLabel("Linhas por slide"), self.max_lines)

        look = QFormLayout()
        look.addRow(BodyLabel("Tema"), self.theme_combo)
        look.addRow(BodyLabel("Cor de destaque"), self.accent_button)

        diagnostic = CardWidget()
        dlayout = QVBoxLayout(diagnostic)
        dlayout.setContentsMargins(20, 16, 20, 16)
        dlayout.addWidget(SubtitleLabel("Diagnóstico"))
        dlayout.addLayout(self.diagnostic_layout)
        dlayout.addWidget(self.refresh_diagnostic_button, 0, Qt.AlignmentFlag.AlignLeft)

        content = QWidget()
        content.setObjectName("settings-content")
        column = QVBoxLayout(content)
        column.setContentsMargins(36, 8, 36, 28)
        column.setSpacing(16)
        column.addWidget(self._card("Provedor de IA", ai))
        column.addWidget(self._card("Pastas e programas", paths))
        column.addWidget(self._card("Tipografia dos cantos", typo))
        column.addWidget(self._card("Aparência", look))
        column.addWidget(diagnostic)
        column.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignLeft)
        column.addStretch(1)

        scroll = ScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(ScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("ScrollArea{background:transparent;border:none}")
        content.setStyleSheet("#settings-content{background:transparent}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 28, 36, 0)
        outer.addWidget(TitleLabel("Configurações"))
        outer.addWidget(scroll, 1)

    # ---- values -------------------------------------------------------------------------

    def _fill(self, s: Settings) -> None:
        self.provider_combo.setCurrentIndex(max(0, self.provider_combo.findData(s.llm_provider)))
        self.openai_model.setText(s.openai_model)
        self.anthropic_model.setText(s.anthropic_model)
        self.output_dir.set_path(s.output_dir)
        self.soffice.set_path(s.soffice_path or self._service.detected_soffice())
        self.template.set_path(s.template_path)
        self.fonts_dir.set_path(s.fonts_dir)
        self.min_font.setValue(s.typography.min_font)
        self.max_font.setValue(s.typography.max_font)
        self.max_lines.setValue(s.typography.max_lines)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(s.theme)))
        self.accent_button.setColor(QColor(s.accent_color))

    def collect(self) -> Settings:
        """Settings from the form; ``ValueError`` if the typography is inconsistent."""
        typography = TypographyConfig(
            self.min_font.value(), self.max_font.value(), self.max_lines.value()
        )
        soffice = self.soffice.path()
        if soffice == self._service.detected_soffice():
            soffice = None  # keep auto-detection
        return self.settings.model_copy(
            update={
                "llm_provider": self.provider_combo.currentData(),
                "openai_model": self.openai_model.text().strip() or self.settings.openai_model,
                "anthropic_model": self.anthropic_model.text().strip()
                or self.settings.anthropic_model,
                "output_dir": self.output_dir.path(),
                "soffice_path": soffice,
                "template_path": self.template.path(),
                "fonts_dir": self.fonts_dir.path(),
                "typography": typography,
                "theme": self.theme_combo.currentData(),
                "accent_color": self.accent_button.color.name().upper(),
            }
        )

    def save(self) -> None:
        try:
            settings = self.collect()
        except ValueError as error:
            InfoBar.error(
                "Tipografia",
                str(error),
                parent=self.window(),
                duration=5000,
                position=InfoBarPosition.TOP,
            )
            return
        self._service.save(settings)
        self.settings = settings
        self.refresh_diagnostic()
        self.settings_saved.emit(settings)
        InfoBar.success(
            "Configurações",
            "Configurações salvas.",
            parent=self.window(),
            duration=3000,
            position=InfoBarPosition.TOP,
        )

    def _theme_changed(self, *_args: object) -> None:
        apply_theme(str(self.theme_combo.currentData()), self.accent_button.color.name().upper())

    # ---- diagnostic ---------------------------------------------------------------------

    def refresh_diagnostic(self) -> None:
        """Re-run the checks with the values currently in the form."""
        try:
            settings = self.collect()
        except ValueError:
            settings = self.settings
        items = self._service.diagnose(settings)
        while self.diagnostic_layout.count():
            child = self.diagnostic_layout.takeAt(0)
            widget = child.widget() if child else None
            if widget is not None:
                widget.deleteLater()
        self.diagnostic_rows = []
        for item in items:
            mark = "✔" if item.ok else "✘"
            box = QWidget()
            column = QVBoxLayout(box)
            column.setContentsMargins(0, 4, 0, 4)
            column.setSpacing(2)
            head = StrongBodyLabel(f"{mark}  {item.name}")
            head.setObjectName("diagnostic-ok" if item.ok else "diagnostic-fail")
            column.addWidget(head)
            detail = BodyLabel(item.detail)
            detail.setWordWrap(True)
            column.addWidget(detail)
            if item.hint and not item.ok:
                hint = CaptionLabel(item.hint)
                hint.setWordWrap(True)
                column.addWidget(hint)
            self.diagnostic_layout.addWidget(box)
            self.diagnostic_rows.append((item, detail))
