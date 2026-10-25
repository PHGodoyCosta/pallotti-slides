"""Nova Missa: the four-step page (Dados → Liturgia → Cantos → Revisão)."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (
    CardWidget,
    FluentIcon,
    PrimaryPushButton,
    PushButton,
    SegmentedWidget,
    SmoothScrollArea,
    StateToolTip,
    SubtitleLabel,
    TitleLabel,
    TransparentToolButton,
)

from pallotti_slides.application.generate_mass import GenerationResult
from pallotti_slides.application.new_mass import (
    IntakeResult,
    LiturgyFields,
    MomentResult,
    NewMassService,
    SongCandidate,
    assemble_mass,
    extracted_fields,
)
from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Mass, Notice, Song
from pallotti_slides.ui.components.progress_chat import MessageKind, ProgressChat
from pallotti_slides.ui.components.repertoire_confirm import ConfirmItem
from pallotti_slides.ui.components.song_editor import SaveScope, SongEditor
from pallotti_slides.ui.pages.new_mass.step_data import StepData
from pallotti_slides.ui.pages.new_mass.step_liturgy import StepLiturgy
from pallotti_slides.ui.pages.new_mass.step_review import StepReview
from pallotti_slides.ui.pages.new_mass.step_songs import StepSongs
from pallotti_slides.ui.tasks import ProgressCallback, Task, start_task

STEP_TITLES = ("1. Dados", "2. Liturgia", "3. Cantos", "4. Revisão")
DATA, LITURGY, SONGS, REVIEW = range(4)
CHAT_WIDTH = 300


class _Job(QObject):
    """Receives the signals of one ``Task`` on the UI thread (a QObject slot is queued)."""

    def __init__(
        self,
        page: "NewMassPage",
        on_done: Callable[[Any], None],
        on_fail: Callable[[str], None] | None,
    ) -> None:
        super().__init__(page)
        self._page = page
        self._on_done = on_done
        self._on_fail = on_fail
        self.task: Task | None = None

    @Slot(str)
    def progress(self, text: str) -> None:
        self._page.say(text)

    @Slot(object)
    def finished(self, result: object) -> None:
        self._page._job_ended(self, ok=True)
        self._on_done(result)

    @Slot(str)
    def failed(self, message: str) -> None:
        self._page._job_ended(self, ok=False)
        self._page.say(message, "error")
        if self._on_fail is not None:
            self._on_fail(message)


class NewMassPage(QWidget):
    """Guides the user through the four steps; long work always runs in a ``Task``."""

    def __init__(self, service: NewMassService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("new-mass-page")
        self._service = service
        self._jobs: list[_Job] = []
        self._tip: StateToolTip | None = None
        self._step = DATA
        self._max_step = DATA
        self._prayers_loaded = False
        self._intake_key: tuple[object, ...] | None = None
        self._resolved_text: dict[SongMoment, str] = {}
        self._moment_notices: dict[SongMoment, list[Notice]] = {}
        self._intake_notices: list[Notice] = []

        self.data_step = StepData()
        self.liturgy_step = StepLiturgy()
        self.songs_step = StepSongs()
        self.review_step = StepReview()
        self.data_step.set_date(service.default_date())
        self.review_step.set_output_dir(service.default_output_dir())

        self.pivot = SegmentedWidget()
        for index, title in enumerate(STEP_TITLES):
            self.pivot.addItem(f"step{index}", title, lambda _=False, i=index: self._pivot(i))
        self.pivot.setCurrentItem("step0")

        data_scroll = SmoothScrollArea()
        data_scroll.setWidget(self.data_step)
        data_scroll.setWidgetResizable(True)
        data_scroll.setStyleSheet("background: transparent; border: none;")
        self.data_step.setStyleSheet("StepData { background: transparent; }")
        self.stack = QStackedWidget()
        for widget in (data_scroll, self.liturgy_step, self.songs_step, self.review_step):
            self.stack.addWidget(widget)

        self.back_button = PushButton(FluentIcon.LEFT_ARROW, "Voltar")
        self.next_button = PrimaryPushButton(FluentIcon.RIGHT_ARROW, "Avançar")
        self.back_button.clicked.connect(self._back)
        self.next_button.clicked.connect(self._next)
        nav = QHBoxLayout()
        nav.addWidget(self.back_button)
        nav.addStretch(1)
        nav.addWidget(self.next_button)

        self.main = QWidget()
        main_layout = QVBoxLayout(self.main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)
        main_layout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(self.stack, 1)
        main_layout.addLayout(nav)

        self.chat = ProgressChat()
        self.chat_hide_button = TransparentToolButton(FluentIcon.CLOSE)
        self.chat_hide_button.setToolTip("Esconder o acompanhamento")
        self.chat_hide_button.clicked.connect(self._hide_chat)
        chat_header = QHBoxLayout()
        chat_header.addWidget(SubtitleLabel("Acompanhamento"))
        chat_header.addStretch(1)
        chat_header.addWidget(self.chat_hide_button)
        self.chat_panel = CardWidget()
        self.chat_panel.setFixedWidth(CHAT_WIDTH)
        chat_layout = QVBoxLayout(self.chat_panel)
        chat_layout.setContentsMargins(8, 8, 8, 8)
        chat_layout.addLayout(chat_header)
        chat_layout.addWidget(self.chat, 1)
        self.chat_panel.hide()

        title_row = QVBoxLayout()
        title_row.setSpacing(12)
        title_row.addWidget(TitleLabel("Nova Missa"))
        title_row.addWidget(self.main, 1)
        root = QHBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(16)
        root.addLayout(title_row, 1)
        root.addWidget(self.chat_panel)

        self.liturgy_step.changed.connect(self._liturgy_changed)
        self.songs_step.resolve_requested.connect(self._resolve_one)
        self.songs_step.candidate_chosen.connect(self._choose_candidate)
        self.songs_step.edit_requested.connect(self._edit)
        self.songs_step.clear_requested.connect(self._clear_moment)
        self.songs_step.assignments_confirmed.connect(self._apply_assignments)
        self.songs_step.confirmation_cancelled.connect(self._confirmation_cancelled)
        self.songs_step.stack.currentChanged.connect(lambda _i: self._sync_nav())
        self.review_step.generate_requested.connect(self._generate)
        self._show_step(DATA)

    # ============================================================== public API ============

    def _hide_chat(self) -> None:
        self.chat_panel.hide()

    def current_step(self) -> int:
        return self._step

    def is_busy(self) -> bool:
        return bool(self._jobs)

    def say(self, text: str, kind: MessageKind = "info") -> None:
        """Write to the progress chat (and show the panel)."""
        self.chat_panel.show()
        self.chat.add_message(text, kind)

    def reset(self) -> None:
        """Back to an empty form (default date, no leaflet, no songs)."""
        self.data_step.set_date(self._service.default_date())
        self.data_step.drop_zone.set_path(None)
        self.data_step.free_text.clear()
        self.data_step.repertoire_edit.clear()
        self._ensure_prayers()
        self.liturgy_step.set_fields(LiturgyFields())
        self.songs_step.clear_all()
        self._resolved_text.clear()
        self._moment_notices.clear()
        self._intake_notices = []
        self._intake_key = None
        self.review_step.hide_result()
        self.chat.clear()
        self._max_step = DATA
        self._show_step(DATA)

    def load_mass(self, mass: Mass, duplicate: bool) -> None:
        """Open ``mass`` for review; ``duplicate`` starts a new Mass (next Sunday) from it."""
        self.reset()
        self.data_step.set_date(
            self._service.default_date() if duplicate else mass.celebration.date
        )
        self.liturgy_step.set_fields(LiturgyFields.from_mass(mass), has_gloria=mass.has_gloria)
        for moment, song in mass.songs.items():
            card = self.songs_step.cards[moment]
            card.set_text(song.title)
            card.set_song(song, "Carregado do histórico")
            self._resolved_text[moment] = card.text()
        self._max_step = REVIEW
        if duplicate:
            self.say(
                "Missa duplicada. Escolha a nova data e revise a liturgia e os cantos "
                "antes de gerar.",
                "question",
            )
            self._show_step(DATA)
        else:
            self.say("Missa carregada do histórico. Confira e gere de novo, se quiser.")
            self._show_step(REVIEW)

    def current_mass(self) -> tuple[Mass | None, list[Notice]]:
        """The Mass in the form now, with every notice the review step would show."""
        date = self.data_step.date()
        if date is None:
            return None, [Notice(level="error", message="Informe uma data válida.", field="date")]
        mass, notices = assemble_mass(
            date,
            self.liturgy_step.fields(),
            self.liturgy_step.has_gloria(),
            self.songs_step.songs(),
        )
        return mass, [*notices, *self._song_notices()]

    def apply_edit(self, moment: SongMoment, song: Song, scope: SaveScope) -> None:
        """Use the edited ``song`` in this Mass and, for ``"library"``, update the library."""
        card = self.songs_step.cards[moment]
        card.set_song(song, "Editada só nesta missa")
        if scope == "library":
            try:
                message = self._service.save_to_library(song)
            except PallottiError as error:
                self.say(str(error), "error")
                return
            card.set_status(f"«{song.title}» — atualizada na biblioteca e nesta missa", "ok")
            self.say(message)
        else:
            self.say(f"«{song.title}» editado só nesta missa (a biblioteca não mudou).")

    # ============================================================== navigation ============

    def _pivot(self, index: int) -> None:
        if index == self._step:
            return
        if self.is_busy() or index > self._max_step:
            self.pivot.setCurrentItem(f"step{self._step}")
            return
        self._show_step(index)

    def _back(self) -> None:
        if self._step > DATA and not self.is_busy():
            self._show_step(self._step - 1)

    def _next(self) -> None:
        if self.is_busy():
            return
        if self._step == DATA:
            self._leave_data()
        elif self._step == LITURGY:
            self._go_forward(SONGS)
        elif self._step == SONGS:
            self._leave_songs()

    def _go_forward(self, index: int) -> None:
        self._max_step = max(self._max_step, index)
        self._show_step(index)

    def _show_step(self, index: int) -> None:
        self._step = index
        self.stack.setCurrentIndex(index)
        self.pivot.setCurrentItem(f"step{index}")
        self.back_button.setEnabled(index > DATA)
        if index == LITURGY:
            self._ensure_prayers()
        elif index == SONGS:
            self.songs_step.set_gloria_enabled(self.liturgy_step.has_gloria())
            if self.songs_step.show_pending_confirmation():
                self.say(
                    "Confirme os momentos dos cantos encontrados antes de continuar.", "question"
                )
        elif index == REVIEW:
            self._enter_review()
        self._sync_nav()

    def _sync_nav(self) -> None:
        """ "Avançar" is hidden on the last step and while a confirmation waits for an answer."""
        confirming = self._step == SONGS and self.songs_step.is_confirming()
        self.next_button.setVisible(self._step < REVIEW and not confirming)
        self.back_button.setVisible(not confirming)

    # ============================================================== step 1: data ==========

    def _ensure_prayers(self) -> None:
        if self._prayers_loaded:
            return
        try:
            prayers = self._service.available_prayers()
        except PallottiError as error:
            self.say(str(error), "error")
            return
        self.liturgy_step.set_prayers(prayers)
        self._prayers_loaded = True

    def _leave_data(self) -> None:
        if not self.data_step.validate_date():
            self.say("Escolha uma data válida para continuar.", "error")
            return
        date = self.data_step.date()
        assert date is not None
        leaflet = self.data_step.leaflet_path()
        free_text = self.data_step.free_text_value()
        url = self.data_step.repertoire_url()
        key = (date, leaflet, free_text, url)
        self._ensure_prayers()
        if (leaflet is None and not free_text and not url) or key == self._intake_key:
            self._go_forward(LITURGY)
            return
        self.say("Vou ler os dados informados. Você pode acompanhar por aqui.")
        self._run(
            "Lendo os dados",
            lambda report: self._service.process_inputs(date, leaflet, free_text, url, report),
            lambda result: self._intake_done(result, key),
        )

    def _intake_done(self, result: IntakeResult, key: tuple[object, ...]) -> None:
        self._intake_key = key
        self._intake_notices = result.notices
        for notice in result.notices:
            if notice.field == "date" or notice.level == "error":
                self.say(notice.message, "error" if notice.level == "error" else "info")
        if result.leaflet is not None:
            fields = LiturgyFields.from_leaflet(result.leaflet)
            previous = self.liturgy_step.fields()
            fields = LiturgyFields(**{**fields.__dict__, "short_title": previous.short_title})
            self.liturgy_step.set_fields(fields, extracted_fields(result.leaflet))
            missing = self.liturgy_step.mark_missing()
            if missing:
                self.say(
                    f"{len(missing)} campo(s) da liturgia não foram encontrados no folheto; "
                    "eles estão destacados para você preencher.",
                    "question",
                )
        items = [ConfirmItem.from_request(r) for r in result.requests]
        if result.proposal is not None:
            items.extend(ConfirmItem.from_proposed(p) for p in result.proposal.items)
        self.songs_step.set_pending_confirmation(items)
        if items:
            where = " e ".join(
                name
                for name, present in (
                    ("do repertório", result.proposal is not None),
                    ("do texto livre", bool(result.requests)),
                )
                if present
            )
            self.say(
                f"Encontrei {len(items)} canto(s) {where}. Na etapa Cantos você confirma o "
                "momento de cada um; nada é preenchido antes disso.",
                "question",
            )
        self._go_forward(LITURGY)

    # ============================================================== step 3: songs =========

    def _leave_songs(self) -> None:
        if self.songs_step.is_confirming():
            self.say("Responda à confirmação dos cantos antes de avançar.", "question")
            return
        stale = {
            m: card.text()
            for m, card in self.songs_step.cards.items()
            if card.text() and card.text() != self._resolved_text.get(m)
        }
        if stale:
            self.say("Alguns cantos digitados ainda não foram buscados; vou buscá-los agora.")
            self._resolve(stale, then_review=True)
            return
        self._go_forward(REVIEW)

    def _resolve_one(self, moment: object, text: str) -> None:
        if isinstance(moment, SongMoment) and not self.is_busy():
            self._resolve({moment: text})

    def _resolve(self, assignments: dict[SongMoment, str], *, then_review: bool = False) -> None:
        self._run(
            "Buscando cantos",
            lambda report: self._service.resolve_many(assignments, report),
            lambda results: self._resolved(results, then_review),
        )

    def _resolved(self, results: dict[SongMoment, MomentResult], then_review: bool) -> None:
        self._apply_results(results)
        if then_review and not self.songs_step.is_confirming():
            self._go_forward(REVIEW)

    def _apply_results(self, results: dict[SongMoment, MomentResult]) -> None:
        for moment, result in results.items():
            card = self.songs_step.cards[moment]
            card.set_result(result)
            self._resolved_text[moment] = result.text
            self._moment_notices[moment] = result.notices
            if result.song is None and result.candidates:
                self.say(
                    f"{moment.label}: qual destes é «{result.text[:60]}»? Escolha no cartão.",
                    "question",
                )
            elif result.song is None:
                for notice in result.notices:
                    self.say(notice.message, "error" if notice.level == "error" else "info")

    def _choose_candidate(self, moment: object, candidate: object) -> None:
        if not (isinstance(moment, SongMoment) and isinstance(candidate, SongCandidate)):
            return
        if self.is_busy():
            return
        text = self.songs_step.cards[moment].text()
        self._run(
            "Obtendo o canto escolhido",
            lambda report: self._choose(moment, text, candidate, report),
            lambda result: self._apply_results({moment: result}),
        )

    def _choose(
        self, moment: SongMoment, text: str, candidate: SongCandidate, report: ProgressCallback
    ) -> MomentResult:
        report(f"{moment.label}: baixando «{candidate.title}»…")
        return self._service.choose_candidate(moment, text, candidate)

    def _clear_moment(self, moment: object) -> None:
        if isinstance(moment, SongMoment):
            self._resolved_text.pop(moment, None)
            self._moment_notices.pop(moment, None)

    def _edit(self, moment: object) -> None:
        if not isinstance(moment, SongMoment):
            return
        song = self.songs_step.cards[moment].song()
        if song is None:
            return
        editor = SongEditor(song, self.window())
        if editor.exec():
            self.apply_edit(moment, editor.result_song(), editor.scope)

    def _apply_assignments(self, assignments: object) -> None:
        if not isinstance(assignments, dict) or not assignments:
            self.say("Nenhum canto foi preenchido.")
            return
        texts: dict[SongMoment, str] = {}
        for moment, item in assignments.items():
            if isinstance(moment, SongMoment) and isinstance(item, ConfirmItem):
                card = self.songs_step.cards[moment]
                card.clear()
                card.set_text(item.text)
                texts[moment] = item.text
        self.say(f"Preenchendo {len(texts)} canto(s) confirmados…")
        self._resolve(texts)

    def _confirmation_cancelled(self) -> None:
        self.say("Tudo bem: nenhum canto foi preenchido. Informe-os um a um nos cartões.")

    # ============================================================== step 2/4: review =====

    def _liturgy_changed(self) -> None:
        self.songs_step.set_gloria_enabled(self.liturgy_step.has_gloria())
        if self._step == REVIEW:
            self._enter_review()

    def _song_notices(self) -> list[Notice]:
        notices: list[Notice] = []
        if self.songs_step.is_confirming() or self.songs_step.has_pending_confirmation():
            notices.append(
                Notice(
                    level="warning",
                    message="Há cantos aguardando a sua confirmação na etapa Cantos.",
                    field="songs",
                )
            )
        for moment, card in self.songs_step.cards.items():
            if card.song() is None and card.candidates():
                notices.append(
                    Notice(
                        level="warning",
                        message=f"{moment.label}: escolha uma das possibilidades encontradas.",
                        field=f"songs.{moment.value}",
                    )
                )
            elif card.song() is None and card.text():
                notices.append(
                    Notice(
                        level="warning",
                        message=(
                            f"{moment.label}: o canto digitado não foi encontrado e será omitido."
                        ),
                        field=f"songs.{moment.value}",
                    )
                )
            elif card.song() is not None:
                notices.extend(
                    Notice(level="warning", message=n.message, field=n.field)
                    for n in self._moment_notices.get(moment, [])
                    if n.level != "info"
                )
        return notices

    def _enter_review(self) -> None:
        mass, notices = self.current_mass()
        self.review_step.hide_result()
        self.review_step.set_notices(notices)
        if mass is not None:
            self.review_step.set_summary(
                f"{mass.celebration.title or '(sem título)'} — {mass.celebration.date:%d/%m/%Y} — "
                f"OE {mass.liturgy.eucharistic_prayer.label} — {len(mass.songs)} canto(s)"
            )
        else:
            self.review_step.set_summary("Faltam dados para montar a missa.")

    def _generate(self) -> None:
        mass, notices = self.current_mass()
        if mass is None or any(n.level == "error" for n in notices) or self.is_busy():
            return
        folder = self.review_step.output_dir()
        self.review_step.hide_result()
        self.say("Vou gerar o PowerPoint e o PDF.")
        self._run(
            "Gerando os slides",
            lambda report: self._service.generate(mass, folder, report),
            lambda result: self._generated(result, notices),
        )

    def _generated(self, result: GenerationResult, notices: list[Notice]) -> None:
        self.review_step.set_notices([*notices, *result.notices])
        self.review_step.show_result(result.pptx, result.pdf)
        self.say(f"Pronto! PowerPoint: {result.pptx}")
        if result.pdf is not None:
            self.say(f"PDF: {result.pdf}")

    # ============================================================== tasks =================

    def _run(
        self,
        title: str,
        function: Callable[[ProgressCallback], object],
        on_done: Callable[[Any], None],
        on_fail: Callable[[str], None] | None = None,
    ) -> None:
        job = _Job(self, on_done, on_fail)
        task = Task(function)
        task.signals.progress.connect(job.progress)
        task.signals.finished.connect(job.finished)
        task.signals.failed.connect(job.failed)
        job.task = task
        self._jobs.append(job)
        self._set_busy(True)
        self._show_tip(title)
        start_task(task)

    def _job_ended(self, job: _Job, *, ok: bool) -> None:
        if job in self._jobs:
            self._jobs.remove(job)
        job.deleteLater()
        if self._tip is not None:
            if ok:
                self._tip.setState(True)
            else:
                self._tip.close()
            self._tip = None
        if not self._jobs:
            self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.main.setEnabled(not busy)
        self.review_step.set_busy(busy)

    def _show_tip(self, title: str) -> None:
        if self._tip is not None:
            self._tip.close()
        tip = StateToolTip(title, "Aguarde, isto pode levar alguns instantes…", self)
        tip.move(max(self.width() - CHAT_WIDTH - tip.width() - 48, 8), 8)
        tip.show()
        self._tip = tip
