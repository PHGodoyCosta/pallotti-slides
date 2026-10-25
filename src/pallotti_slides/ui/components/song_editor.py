"""Song editor: stanzas, verse/chorus, bold per line and execution order (SPEC F7)."""

from typing import Literal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    FluentIcon,
    LineEdit,
    MessageBoxBase,
    PushButton,
    SmoothScrollArea,
    SubtitleLabel,
    TransparentToolButton,
)

from pallotti_slides.domain.enums import StanzaType
from pallotti_slides.domain.models import Line, Song, Stanza

SaveScope = Literal["mass", "library"]

_TYPE_LABELS = {StanzaType.VERSE: "Verso", StanzaType.CHORUS: "Refrão"}


class _LineRow(QWidget):
    """One line of a stanza: text plus a bold toggle."""

    def __init__(self, line: Line, on_remove: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.edit = LineEdit()
        self.edit.setText(line.text)
        self.edit.setClearButtonEnabled(False)
        self.bold = CheckBox("Negrito")
        self.bold.setChecked(line.bold)
        self.remove_button = TransparentToolButton(FluentIcon.REMOVE)
        self.remove_button.setToolTip("Remover linha")
        self.remove_button.clicked.connect(on_remove)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.bold)
        layout.addWidget(self.remove_button)

    def line(self) -> Line:
        return Line(text=self.edit.text().strip(), bold=self.bold.isChecked())


class StanzaEditor(CardWidget):  # type: ignore[misc]
    """A stanza: type selector, editable lines and an "add line" button."""

    changed = Signal()

    def __init__(self, stanza: Stanza, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.stanza_id = stanza.id
        self.type_combo = ComboBox()
        for stanza_type in StanzaType:
            self.type_combo.addItem(_TYPE_LABELS[stanza_type], userData=stanza_type)
        self.type_combo.setCurrentIndex(list(StanzaType).index(stanza.type))
        self.title_label = BodyLabel("")
        self.remove_button = PushButton(FluentIcon.DELETE, "Remover estrofe")
        self.add_line_button = PushButton(FluentIcon.ADD, "Adicionar linha")
        self.add_line_button.clicked.connect(lambda: self.add_line(Line(text="")))

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addWidget(self.type_combo)
        header.addStretch(1)
        header.addWidget(self.remove_button)

        self._rows = QVBoxLayout()
        self._rows.setSpacing(6)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addLayout(self._rows)
        layout.addWidget(self.add_line_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.rows: list[_LineRow] = []
        for line in stanza.lines:
            self.add_line(line)

    def add_line(self, line: Line) -> None:
        row: _LineRow

        def remove() -> None:
            self.rows.remove(row)
            row.deleteLater()

        row = _LineRow(line, remove)
        row.edit.textChanged.connect(lambda _t: self.changed.emit())
        self.rows.append(row)
        self._rows.addWidget(row)

    def stanza_type(self) -> StanzaType:
        return StanzaType(self.type_combo.currentData())

    def stanza(self) -> Stanza:
        lines = [row.line() for row in self.rows if row.edit.text().strip()]
        return Stanza(id=self.stanza_id, type=self.stanza_type(), lines=lines)


class SongEditor(MessageBoxBase):  # type: ignore[misc]
    """Edit a copy of a ``Song``. ``scope`` tells where the user wants it saved.

    Use ``exec()``; on accept read ``result_song()`` and ``scope`` (``"mass"``: only this Mass;
    ``"library"``: also update the song library).
    """

    def __init__(self, song: Song, parent: QWidget) -> None:
        super().__init__(parent)
        self.scope: SaveScope = "mass"
        self._next_id = max((s.id for s in song.stanzas), default=0) + 1
        self._source = song
        self.stanza_editors: list[StanzaEditor] = []

        self.viewLayout.addWidget(SubtitleLabel("Editar letra"))
        self.title_edit = LineEdit()
        self.title_edit.setText(song.title)
        self.title_edit.setPlaceholderText("Título do canto")
        self.viewLayout.addWidget(self.title_edit)

        self._stanzas_layout = QVBoxLayout()
        self._stanzas_layout.setSpacing(10)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.addLayout(self._stanzas_layout)
        self.add_verse_button = PushButton(FluentIcon.ADD, "Adicionar estrofe")
        self.add_verse_button.clicked.connect(lambda: self.add_stanza(StanzaType.VERSE))
        body_layout.addWidget(self.add_verse_button, 0, Qt.AlignmentFlag.AlignLeft)
        body_layout.addStretch(1)
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidget(body)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        body.setStyleSheet("background: transparent;")
        self.scroll_area.setMinimumHeight(260)
        self.viewLayout.addWidget(self.scroll_area, 1)

        self.viewLayout.addWidget(BodyLabel("Ordem de execução (arraste para reordenar)"))
        self.order_list = QListWidget()
        self.order_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.order_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.order_list.setFixedHeight(120)
        self.viewLayout.addWidget(self.order_list)
        order_buttons = QHBoxLayout()
        self.repeat_button = PushButton(FluentIcon.ADD, "Repetir estrofe selecionada")
        self.drop_button = PushButton(FluentIcon.REMOVE, "Tirar da ordem")
        self.repeat_button.clicked.connect(self._repeat_selected)
        self.drop_button.clicked.connect(self._drop_selected)
        order_buttons.addWidget(self.repeat_button)
        order_buttons.addWidget(self.drop_button)
        order_buttons.addStretch(1)
        self.viewLayout.addLayout(order_buttons)
        self.viewLayout.addWidget(
            CaptionLabel("«Salvar só nesta missa» não altera o canto da biblioteca.")
        )

        for stanza in song.stanzas:
            self._add_editor(stanza)
        for stanza_id in song.order or [s.id for s in song.stanzas]:
            self._add_order_item(stanza_id)
        self._refresh_labels()

        self.yesButton.setText("Salvar só nesta missa")
        self.library_button = PushButton("Atualizar na biblioteca")
        self.library_button.clicked.connect(self.save_to_library)
        self.buttonLayout.insertWidget(1, self.library_button, 1, Qt.AlignmentFlag.AlignVCenter)
        self.cancelButton.setText("Cancelar")
        self.widget.setMinimumWidth(760)

    # -- stanzas -------------------------------------------------------------------------

    def add_stanza(self, stanza_type: StanzaType) -> int:
        """Append an empty stanza (with one empty line) and put it at the end of the order."""
        stanza = Stanza(id=self._next_id, type=stanza_type, lines=[Line(text="")])
        self._next_id += 1
        self._add_editor(stanza)
        self._add_order_item(stanza.id)
        self._refresh_labels()
        return stanza.id

    def remove_stanza(self, stanza_id: int) -> None:
        """Delete the stanza and every place it appears in the order."""
        for editor in list(self.stanza_editors):
            if editor.stanza_id == stanza_id:
                self.stanza_editors.remove(editor)
                editor.deleteLater()
        for row in reversed(range(self.order_list.count())):
            item = self.order_list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == stanza_id:
                self.order_list.takeItem(row)
        self._refresh_labels()

    def _add_editor(self, stanza: Stanza) -> None:
        editor = StanzaEditor(stanza)
        editor.remove_button.clicked.connect(lambda: self.remove_stanza(editor.stanza_id))
        editor.type_combo.currentIndexChanged.connect(lambda _i: self._refresh_labels())
        editor.changed.connect(self._refresh_labels)
        self.stanza_editors.append(editor)
        self._stanzas_layout.addWidget(editor)

    # -- order ---------------------------------------------------------------------------

    def order(self) -> list[int]:
        """Stanza ids in execution order as shown in the list."""
        ids: list[int] = []
        for row in range(self.order_list.count()):
            item = self.order_list.item(row)
            if item is not None:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def _add_order_item(self, stanza_id: int) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, stanza_id)
        self.order_list.addItem(item)

    def _repeat_selected(self) -> None:
        item = self.order_list.currentItem()
        if item is not None:
            self._add_order_item(int(item.data(Qt.ItemDataRole.UserRole)))
            self._refresh_labels()

    def _drop_selected(self) -> None:
        row = self.order_list.currentRow()
        if row >= 0:
            self.order_list.takeItem(row)

    def _refresh_labels(self) -> None:
        names: dict[int, str] = {}
        for number, editor in enumerate(self.stanza_editors, start=1):
            kind = _TYPE_LABELS[editor.stanza_type()]
            editor.title_label.setText(f"Estrofe {number}")
            first = next((r.edit.text().strip() for r in editor.rows if r.edit.text().strip()), "")
            names[editor.stanza_id] = f"{number}. {kind}: {first[:48]}"
        for row in range(self.order_list.count()):
            item = self.order_list.item(row)
            if item is not None:
                stanza_id = int(item.data(Qt.ItemDataRole.UserRole))
                item.setText(names.get(stanza_id, "?"))

    # -- result --------------------------------------------------------------------------

    def save_to_library(self) -> None:
        """Accept with the "update library" scope."""
        if self.validate():
            self.scope = "library"
            self.accept()

    def validate(self) -> bool:
        return bool(self.title_edit.text().strip()) and any(
            row.edit.text().strip() for editor in self.stanza_editors for row in editor.rows
        )

    def result_song(self) -> Song:
        """The edited song (stanzas without text are dropped, and so is their order)."""
        stanzas = [editor.stanza() for editor in self.stanza_editors]
        stanzas = [stanza for stanza in stanzas if stanza.lines]
        known = {stanza.id for stanza in stanzas}
        order = [stanza_id for stanza_id in self.order() if stanza_id in known]
        return self._source.model_copy(
            update={
                "title": self.title_edit.text().strip(),
                "stanzas": stanzas,
                "order": order or [stanza.id for stanza in stanzas],
            }
        )
