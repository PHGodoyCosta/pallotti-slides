"""Step 2 — Liturgia: form for Celebration and Liturgy (SPEC F3)."""

from typing import Literal, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    LineEdit,
    SmoothScrollArea,
    StrongBodyLabel,
    SwitchButton,
)

from pallotti_slides.application.new_mass import LiturgyFields
from pallotti_slides.domain.enums import EucharisticPrayer, LiturgicalSeason
from pallotti_slides.domain.rules import default_has_gloria

SEASON_LABELS: dict[LiturgicalSeason, str] = {
    LiturgicalSeason.ADVENT: "Advento",
    LiturgicalSeason.CHRISTMAS: "Natal",
    LiturgicalSeason.LENT: "Quaresma",
    LiturgicalSeason.PASCHAL_TRIDUUM: "Tríduo Pascal",
    LiturgicalSeason.EASTER: "Páscoa",
    LiturgicalSeason.ORDINARY_TIME: "Tempo Comum",
}
EXTRACTED_TEXT = "extraído do folheto — confira"
MISSING_TEXT = "não encontrado — preencha"
_EXTRACTED_COLOR = "#1F5FA8"
_MISSING_COLOR = "#C42B1C"

# (attribute of LiturgyFields, label, required, placeholder)
_TEXT_FIELDS: list[tuple[str, str, bool, str]] = [
    ("title", "Título da celebração", True, "Ex.: 30° Domingo do Tempo Comum"),
    ("short_title", "Título curto (opcional)", False, "Em branco = automático (Dom / T.C)"),
    ("first_reading", "1ª leitura", True, "Ex.: Ex 22,20-26"),
    ("psalm_number", "Número do salmo", True, "Ex.: 17(18)"),
    ("psalm_refrain", "Refrão do salmo", True, ""),
    ("second_reading", "2ª leitura (se houver)", False, "Ex.: 1Ts 1,5c-10"),
    ("gospel", "Evangelho", True, "Ex.: Mt 22,34-40"),
    ("intercessions_response", "Refrão das preces", True, ""),
    ("mystery_of_faith", "Aclamação do mistério da fé", True, "Texto do folheto"),
]


class _FieldRow(QWidget):
    """Label + editor + a small tag ("extraído do folheto" / "não encontrado")."""

    def __init__(self, key: str, label: str, required: bool, editor: QWidget) -> None:
        super().__init__()
        self.key = key
        self.required = required
        self.editor = editor
        self.tag = CaptionLabel("")
        self.tag.hide()
        caption = BodyLabel(label + (" *" if required else ""))
        caption.setFixedWidth(210)
        right = QVBoxLayout()
        right.setSpacing(2)
        if isinstance(editor, LineEdit):
            right.addWidget(editor)
        else:  # combos and the switch keep their natural width, aligned to the left
            editor.setMinimumWidth(260 if isinstance(editor, ComboBox) else 0)
            right.addWidget(editor, 0, Qt.AlignmentFlag.AlignLeft)
        right.addWidget(self.tag)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(caption, 0)
        layout.addLayout(right, 1)

    def mark(self, kind: Literal["extracted", "missing", "none"], text: str = "") -> None:
        if kind == "none":
            self.tag.hide()
        else:
            color = _EXTRACTED_COLOR if kind == "extracted" else _MISSING_COLOR
            self.tag.setText(text or (EXTRACTED_TEXT if kind == "extracted" else MISSING_TEXT))
            self.tag.setStyleSheet(f"color: {color};")
            self.tag.show()
        if isinstance(self.editor, LineEdit):
            self.editor.setError(kind == "missing")
            self.editor.setStyleSheet(
                f"LineEdit {{ border: 1px solid {_MISSING_COLOR}; "
                f"border-bottom: 2px solid {_MISSING_COLOR}; "
                "background: rgba(196, 43, 28, 0.08); }"
                if kind == "missing"
                else ""
            )
        elif isinstance(self.editor, ComboBox):
            self.editor.setStyleSheet(
                f"ComboBox {{ border: 1px solid {_MISSING_COLOR}; }}" if kind == "missing" else ""
            )


class StepLiturgy(QWidget):
    """The liturgy form; ``fields()`` / ``set_fields()`` exchange ``LiturgyFields``."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step-liturgy")
        self._rows: dict[str, _FieldRow] = {}
        self.edits: dict[str, LineEdit] = {}

        self.season_combo = ComboBox()
        for season, label in SEASON_LABELS.items():
            self.season_combo.addItem(label, userData=season)
        self.season_combo.setCurrentIndex(list(SEASON_LABELS).index(LiturgicalSeason.ORDINARY_TIME))
        self.year_combo = ComboBox()
        for text in ("—", "A", "B", "C"):
            self.year_combo.addItem(text, userData=None if text == "—" else text)
        self.prayer_combo = ComboBox()
        self.prayer_combo.addItem("Escolha a Oração Eucarística…", userData=None)
        self.gloria_switch = SwitchButton()
        self.gloria_switch.setOnText("Tem Glória")
        self.gloria_switch.setOffText("Sem Glória")
        self.gloria_switch.setChecked(default_has_gloria(LiturgicalSeason.ORDINARY_TIME))
        self._last_season = LiturgicalSeason.ORDINARY_TIME

        body = QWidget()
        form = QVBoxLayout(body)
        form.setContentsMargins(0, 0, 12, 0)
        form.setSpacing(10)
        form.addWidget(StrongBodyLabel("Celebração"))
        for key, label, required, placeholder in _TEXT_FIELDS[:2]:
            form.addWidget(self._text_row(key, label, required, placeholder))
        form.addWidget(self._row("season", "Tempo litúrgico", True, self.season_combo))
        form.addWidget(self._row("year", "Ano (A, B ou C)", False, self.year_combo))
        form.addSpacing(8)
        form.addWidget(StrongBodyLabel("Liturgia da Palavra"))
        for key, label, required, placeholder in _TEXT_FIELDS[2:8]:
            form.addWidget(self._text_row(key, label, required, placeholder))
        form.addSpacing(8)
        form.addWidget(StrongBodyLabel("Liturgia Eucarística"))
        form.addWidget(
            self._row("eucharistic_prayer", "Oração Eucarística", True, self.prayer_combo)
        )
        form.addWidget(self._text_row(*_TEXT_FIELDS[8]))
        form.addWidget(self._row("has_gloria", "Glória", False, self.gloria_switch))
        form.addStretch(1)

        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidget(body)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        body.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)

        self.season_combo.currentIndexChanged.connect(self._season_changed)
        for combo in (self.year_combo, self.prayer_combo):
            combo.currentIndexChanged.connect(lambda _i: self._edited())
        self.gloria_switch.checkedChanged.connect(lambda _c: self.changed.emit())

    # -- building ------------------------------------------------------------------------

    def _row(self, key: str, label: str, required: bool, editor: QWidget) -> _FieldRow:
        row = _FieldRow(key, label, required, editor)
        self._rows[key] = row
        return row

    def _text_row(self, key: str, label: str, required: bool, placeholder: str) -> _FieldRow:
        edit = LineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setClearButtonEnabled(True)
        edit.textChanged.connect(lambda _t, k=key: self._text_edited(k))
        self.edits[key] = edit
        return self._row(key, label, required, edit)

    # -- reading and writing -------------------------------------------------------------

    def set_prayers(self, prayers: list[EucharisticPrayer]) -> None:
        """Offer only the prayers that exist in the template (keeps the current choice)."""
        current = self.prayer()
        self.prayer_combo.blockSignals(True)
        self.prayer_combo.clear()
        self.prayer_combo.addItem("Escolha a Oração Eucarística…", userData=None)
        for prayer in prayers:
            self.prayer_combo.addItem(f"OE {prayer.label}", userData=prayer)
        self.prayer_combo.blockSignals(False)
        self._select_prayer(current)

    def prayers(self) -> list[EucharisticPrayer]:
        found = (self.prayer_combo.itemData(i) for i in range(1, self.prayer_combo.count()))
        return [prayer for prayer in found if isinstance(prayer, EucharisticPrayer)]

    def prayer(self) -> EucharisticPrayer | None:
        data = self.prayer_combo.currentData()
        return data if isinstance(data, EucharisticPrayer) else None

    def _select_prayer(self, prayer: EucharisticPrayer | None) -> bool:
        for index in range(self.prayer_combo.count()):
            if self.prayer_combo.itemData(index) == prayer:
                self.prayer_combo.setCurrentIndex(index)
                return True
        self.prayer_combo.setCurrentIndex(0)
        return False

    def season(self) -> LiturgicalSeason:
        return cast(LiturgicalSeason, self.season_combo.currentData())

    def has_gloria(self) -> bool:
        return bool(self.gloria_switch.isChecked())

    def set_has_gloria(self, value: bool) -> None:
        self.gloria_switch.setChecked(value)

    def fields(self) -> LiturgyFields:
        values = {key: edit.text() for key, edit in self.edits.items()}
        year = self.year_combo.currentData()
        return LiturgyFields(
            season=self.season(),
            year=year if year in ("A", "B", "C") else None,
            eucharistic_prayer=self.prayer(),
            **values,
        )

    def set_fields(
        self,
        fields: LiturgyFields,
        extracted: set[str] | frozenset[str] = frozenset(),
        *,
        has_gloria: bool | None = None,
    ) -> None:
        """Fill the form. ``extracted`` names the fields that came from the leaflet."""
        for combo in (self.season_combo, self.year_combo, self.prayer_combo):
            combo.blockSignals(True)
        for key, edit in self.edits.items():
            edit.blockSignals(True)
            edit.setText(getattr(fields, key))
            edit.blockSignals(False)
        self.season_combo.setCurrentIndex(list(SEASON_LABELS).index(fields.season))
        self.year_combo.setCurrentIndex(("—", "A", "B", "C").index(fields.year or "—"))
        prayer_found = self._select_prayer(fields.eucharistic_prayer)
        for combo in (self.season_combo, self.year_combo, self.prayer_combo):
            combo.blockSignals(False)
        self._last_season = fields.season
        self.set_has_gloria(default_has_gloria(fields.season) if has_gloria is None else has_gloria)
        for row in self._rows.values():
            row.mark("none")
        for key in extracted:
            found_row = self._rows.get(key)
            if found_row is not None and key != "eucharistic_prayer":
                found_row.mark("extracted")
        if fields.eucharistic_prayer is not None:
            prayer_row = self._rows["eucharistic_prayer"]
            if prayer_found:
                if "eucharistic_prayer" in extracted:
                    prayer_row.mark("extracted")
            else:
                prayer_row.mark(
                    "missing",
                    f"A OE {fields.eucharistic_prayer.label} não existe no modelo; escolha outra.",
                )
        self.changed.emit()

    def mark_missing(self) -> list[str]:
        """Highlight every empty required field; returns their keys."""
        missing: list[str] = []
        for key, row in self._rows.items():
            if not row.required or key in ("season", "has_gloria"):
                continue
            empty = (
                self.prayer() is None
                if key == "eucharistic_prayer"
                else not self.edits[key].text().strip()
            )
            if empty:
                missing.append(key)
                row.mark("missing")
        return missing

    def tag_text(self, key: str) -> str:
        """Visible tag of a field ("" when none); for tests and accessibility."""
        row = self._rows[key]
        return str(row.tag.text()) if not row.tag.isHidden() else ""

    # -- reactions -----------------------------------------------------------------------

    def _season_changed(self, _index: int) -> None:
        # the switch follows the season rule unless the user already changed it by hand
        touched = self.has_gloria() != default_has_gloria(self._last_season)
        self._last_season = self.season()
        if not touched:
            self.set_has_gloria(default_has_gloria(self._last_season))
        self.changed.emit()

    def _text_edited(self, key: str) -> None:
        row = self._rows[key]
        if row.required and self.edits[key].text().strip():
            row.mark("none")
        elif not row.tag.isHidden() and row.tag.text() == EXTRACTED_TEXT:
            row.mark("none")  # edited by hand: no longer "as extracted"
        self.changed.emit()

    def _edited(self) -> None:
        if self.prayer() is not None:
            self._rows["eucharistic_prayer"].mark("none")
        self.changed.emit()
