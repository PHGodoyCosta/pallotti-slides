"""Library page (SPEC F12): search, filter, edit, aliases, merge and delete songs."""

from typing import cast

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    FluentIcon,
    InfoBar,
    LineEdit,
    ListWidget,
    MessageBox,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    StrongBodyLabel,
    SubtitleLabel,
    TextEdit,
    TitleLabel,
)

from pallotti_slides.application.library import LibraryEntry, SongLibrary
from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Notice, Song
from pallotti_slides.domain.text import looks_like_url
from pallotti_slides.ui.components.song_editor import SongEditor
from pallotti_slides.ui.tasks import Task, start_task


class _NewSongDialog(MessageBoxBase):  # type: ignore[misc]
    """Paste the lyrics or an address (Letras / Cifra Club)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.viewLayout.addWidget(SubtitleLabel("Novo canto"))
        self.viewLayout.addWidget(BodyLabel("Cole a letra completa ou o endereço do canto."))
        self.text_edit = TextEdit()
        self.text_edit.setPlaceholderText("Letra do canto ou https://www.letras.mus.br/…")
        self.text_edit.setMinimumSize(460, 220)
        self.viewLayout.addWidget(self.text_edit)
        self.yesButton.setText("Criar")
        self.cancelButton.setText("Cancelar")

    def validate(self) -> bool:
        return bool(self.text_edit.toPlainText().strip())


class _MergeDialog(MessageBoxBase):  # type: ignore[misc]
    """Pick the duplicate that will be merged into the current song."""

    def __init__(self, keep: LibraryEntry, others: list[LibraryEntry], parent: QWidget) -> None:
        super().__init__(parent)
        self.viewLayout.addWidget(SubtitleLabel("Mesclar com…"))
        self.viewLayout.addWidget(
            BodyLabel(
                f"O canto escolhido será apagado; apelidos e histórico\n"
                f"vão para «{keep.song.title}»."
            )
        )
        self.combo = ComboBox()
        for other in others:
            self.combo.addItem(other.song.title, userData=other.id)
        self.combo.setMinimumWidth(380)
        self.viewLayout.addWidget(self.combo)
        self.yesButton.setText("Mesclar")
        self.cancelButton.setText("Cancelar")

    def chosen_id(self) -> int | None:
        data = self.combo.currentData()
        return int(data) if data is not None else None


class LibraryPage(QWidget):
    """Song list on the left; details, aliases, usage and actions on the right."""

    def __init__(self, library: SongLibrary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("library-page")
        self._library = library
        self._entries: list[LibraryEntry] = []
        self._current: LibraryEntry | None = None
        self._draft: Song | None = None
        self._busy: Task | None = None

        # -- left column
        self.search_edit = SearchLineEdit()
        self.search_edit.setPlaceholderText("Buscar por título, apelido ou 1ª linha")
        self.moment_filter = ComboBox()
        self.moment_filter.addItem("Todos os momentos", userData=None)
        for moment in SongMoment:
            self.moment_filter.addItem(moment.label, userData=moment)
        self.song_list = ListWidget()
        self.count_label = CaptionLabel("")
        self.new_button = PrimaryPushButton(FluentIcon.ADD, "Novo")
        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(self.search_edit)
        left.addWidget(self.moment_filter)
        left.addWidget(self.song_list, 1)
        left.addWidget(self.count_label)
        left.addWidget(self.new_button)
        left_box = QWidget()
        left_box.setLayout(left)
        left_box.setFixedWidth(300)
        left.setContentsMargins(0, 0, 0, 0)

        # -- right column
        self.title_label = SubtitleLabel("Selecione um canto")
        self.info_label = BodyLabel("")
        self.usage_label = BodyLabel("")
        self.lyrics_view = TextEdit()
        self.lyrics_view.setReadOnly(True)
        self.edit_button = PushButton(FluentIcon.EDIT, "Editar letra…")

        self.moment_boxes: dict[SongMoment, CheckBox] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        for index, moment in enumerate(SongMoment):
            box = CheckBox(moment.label)
            self.moment_boxes[moment] = box
            grid.addWidget(box, index // 3, index % 3)

        self.alias_list = ListWidget()
        self.alias_list.setFixedHeight(84)
        self.alias_edit = LineEdit()
        self.alias_edit.setPlaceholderText("Novo apelido")
        self.add_alias_button = PushButton(FluentIcon.ADD, "Adicionar")
        self.remove_alias_button = PushButton(FluentIcon.REMOVE, "Remover")
        alias_row = QHBoxLayout()
        alias_row.addWidget(self.alias_edit, 1)
        alias_row.addWidget(self.add_alias_button)
        alias_row.addWidget(self.remove_alias_button)

        self.save_button = PrimaryPushButton(FluentIcon.SAVE, "Salvar")
        self.merge_button = PushButton(FluentIcon.SYNC, "Mesclar com…")
        self.delete_button = PushButton(FluentIcon.DELETE, "Excluir")
        actions = QHBoxLayout()
        for button in (self.save_button, self.merge_button, self.delete_button):
            actions.addWidget(button)
        actions.addStretch(1)

        title_row = QHBoxLayout()
        title_row.addWidget(self.title_label, 1)
        title_row.addWidget(self.edit_button)
        self.detail = QWidget()
        right = QVBoxLayout(self.detail)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(8)
        right.addLayout(title_row)
        right.addWidget(self.info_label)
        right.addWidget(self.usage_label)
        right.addWidget(self.lyrics_view, 1)
        right.addWidget(StrongBodyLabel("Momentos habituais"))
        right.addLayout(grid)
        right.addWidget(StrongBodyLabel("Apelidos"))
        right.addWidget(self.alias_list)
        right.addLayout(alias_row)
        right.addLayout(actions)
        self.empty_label = BodyLabel("A biblioteca está vazia. Use «Novo» para adicionar um canto.")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 28, 24, 16)
        outer.addWidget(TitleLabel("Biblioteca"))
        body = QHBoxLayout()
        body.setSpacing(20)
        body.addWidget(left_box)
        body.addWidget(self.detail, 1)
        outer.addLayout(body, 1)
        outer.addWidget(self.empty_label)

        self.search_edit.textChanged.connect(lambda _t: self.refresh())
        self.moment_filter.currentIndexChanged.connect(lambda _i: self.refresh())
        self.song_list.currentRowChanged.connect(self._on_row)
        self.new_button.clicked.connect(self.new_song)
        self.edit_button.clicked.connect(self.edit_structure)
        self.save_button.clicked.connect(self.save)
        self.merge_button.clicked.connect(self.merge)
        self.delete_button.clicked.connect(self.delete)
        self.add_alias_button.clicked.connect(self.add_alias)
        self.alias_edit.returnPressed.connect(self.add_alias)
        self.remove_alias_button.clicked.connect(self.remove_alias)
        self.detail.setVisible(False)  # the list loads when the page is first shown
        self.empty_label.setVisible(False)

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.refresh()
        super().showEvent(event)

    # -- list ----------------------------------------------------------------------------

    def refresh(self, select_id: int | None = None) -> None:
        """Reload the list (keeps the selection, or selects ``select_id``)."""
        wanted = (
            select_id if select_id is not None else (self._current.id if self._current else None)
        )
        moment = self.moment_filter.currentData()
        self._entries = self._library.list_entries(self.search_edit.text(), moment)
        self.song_list.blockSignals(True)
        self.song_list.clear()
        row_to_select = -1
        for index, entry in enumerate(self._entries):
            self.song_list.addItem(QListWidgetItem(entry.song.title))
            if entry.id == wanted:
                row_to_select = index
        if row_to_select < 0 and self._entries:
            row_to_select = 0
        self.song_list.setCurrentRow(row_to_select)
        self.song_list.blockSignals(False)
        total = len(self._entries)
        self.count_label.setText("1 canto" if total == 1 else f"{total} cantos")
        self._on_row(row_to_select)

    def _on_row(self, row: int) -> None:
        entry = self._entries[row] if 0 <= row < len(self._entries) else None
        self._show(entry)

    def _show(self, entry: LibraryEntry | None) -> None:
        self._current = entry
        self._draft = None
        self.detail.setVisible(entry is not None)
        self.empty_label.setVisible(entry is None and not self._library.list_entries())
        if entry is None:
            return
        self.title_label.setText(entry.song.title)
        parts = [entry.song.artist or "Artista não informado"]
        parts.append("conferido" if entry.reviewed else "não conferido")
        self.info_label.setText(" · ".join(parts))
        self.usage_label.setText(entry.usage_text())
        self._show_lyrics(entry.song)
        for moment, box in self.moment_boxes.items():
            box.setChecked(moment in entry.usual_moments)
        self.alias_list.clear()
        for alias in entry.aliases:
            self.alias_list.addItem(QListWidgetItem(alias))

    def _show_lyrics(self, song: Song) -> None:
        blocks = ["\n".join(line.text for line in stanza.lines) for stanza in song.sequence()]
        self.lyrics_view.setPlainText("\n\n".join(blocks))

    # -- dialogs (replaceable in tests) --------------------------------------------------

    def ask_new_text(self) -> str | None:
        dialog = _NewSongDialog(self.window())
        return dialog.text_edit.toPlainText().strip() if dialog.exec() else None

    def ask_merge_target(self, keep: LibraryEntry, others: list[LibraryEntry]) -> int | None:
        dialog = _MergeDialog(keep, others, self.window())
        return dialog.chosen_id() if dialog.exec() else None

    def confirm_delete(self, entry: LibraryEntry) -> bool:
        box = MessageBox(
            "Excluir canto",
            f"Excluir «{entry.song.title}» da biblioteca? Isso não pode ser desfeito.",
            self.window(),
        )
        box.yesButton.setText("Excluir")
        box.cancelButton.setText("Cancelar")
        return bool(box.exec())

    def edit_song(self, song: Song) -> Song | None:
        editor = SongEditor(song, self.window())
        editor.yesButton.setText("Aplicar")
        editor.library_button.hide()
        return editor.result_song() if editor.exec() else None

    # -- actions -------------------------------------------------------------------------

    def new_song(self) -> None:
        text = self.ask_new_text()
        if not text:
            return
        if looks_like_url(text):
            self._import_url(text)
            return
        try:
            song_id, notices = self._library.create_from_lyrics(text)
        except PallottiError as error:
            self._error(str(error))
            return
        self._created(song_id, notices)

    def _import_url(self, url: str) -> None:
        if self._busy is not None:
            return
        self.new_button.setEnabled(False)
        task = Task(lambda _report: self._library.create_from_url(url))
        task.signals.finished.connect(self._url_done)
        task.signals.failed.connect(self._url_failed)
        self._busy = start_task(task)

    def _url_done(self, result: object) -> None:
        self._busy = None
        self.new_button.setEnabled(True)
        song_id, notices = cast(tuple[int, list[Notice]], result)
        self._created(song_id, notices)

    def _url_failed(self, message: str) -> None:
        self._busy = None
        self.new_button.setEnabled(True)
        self._error(message)

    def _created(self, song_id: int, notices: list[Notice]) -> None:
        self.search_edit.clear()
        self.moment_filter.setCurrentIndex(0)
        self.refresh(select_id=song_id)
        warnings = [n.message for n in notices if n.level != "info"]
        if warnings:
            InfoBar.warning("Canto criado", " ".join(warnings), parent=self.window())
        else:
            InfoBar.success("Biblioteca", "Canto adicionado.", parent=self.window())

    def edit_structure(self) -> None:
        if self._current is None:
            return
        edited = self.edit_song(self._draft or self._current.song)
        if edited is not None:
            self._draft = edited
            self._show_lyrics(edited)
            self.title_label.setText(edited.title)
            InfoBar.info(
                "Biblioteca", "Alterações prontas. Clique em «Salvar».", parent=self.window()
            )

    def selected_moments(self) -> list[SongMoment]:
        return [m for m, box in self.moment_boxes.items() if box.isChecked()]

    def save(self) -> None:
        if self._current is None:
            return
        entry = self._current
        try:
            self._library.update(entry.id, self._draft or entry.song, self.selected_moments())
        except PallottiError as error:
            self._error(str(error))
            return
        self.refresh(select_id=entry.id)
        InfoBar.success("Biblioteca", "Canto salvo.", parent=self.window())

    def add_alias(self) -> None:
        text = self.alias_edit.text().strip()
        if self._current is None or not text:
            return
        try:
            self._library.add_alias(self._current.id, text)
        except (PallottiError, ValueError) as error:
            self._error(str(error))
            return
        self.alias_edit.clear()
        self.refresh()

    def remove_alias(self) -> None:
        item = self.alias_list.currentItem()
        if self._current is None or item is None:
            return
        self._library.remove_alias(self._current.id, item.text())
        self.refresh()

    def merge(self) -> None:
        if self._current is None:
            return
        keep = self._current
        others = [e for e in self._library.list_entries() if e.id != keep.id]
        if not others:
            self._error("Não há outro canto para mesclar.")
            return
        target = self.ask_merge_target(keep, others)
        if target is None:
            return
        try:
            self._library.merge(keep.id, target)
        except PallottiError as error:
            self._error(str(error))
            return
        self.refresh(select_id=keep.id)
        InfoBar.success("Biblioteca", "Cantos mesclados.", parent=self.window())

    def delete(self) -> None:
        if self._current is None or not self.confirm_delete(self._current):
            return
        try:
            self._library.delete(self._current.id)
        except PallottiError as error:
            self._error(str(error))
            return
        self._current = None
        self.refresh()
        InfoBar.success("Biblioteca", "Canto excluído.", parent=self.window())

    def _error(self, message: str) -> None:
        InfoBar.error("Biblioteca", message, parent=self.window())
