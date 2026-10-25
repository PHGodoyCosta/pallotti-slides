import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtCore import QDate
from pytestqt.qtbot import QtBot

from pallotti_slides.application.new_mass import LiturgyFields, NewMassService
from pallotti_slides.domain.enums import (
    EucharisticPrayer,
    LiturgicalSeason,
    SongMoment,
)
from pallotti_slides.domain.models import Line
from pallotti_slides.ui.components.repertoire_confirm import IGNORE
from pallotti_slides.ui.components.song_editor import SongEditor
from pallotti_slides.ui.main_window import MainWindow
from pallotti_slides.ui.pages.new_mass import NewMassPage
from pallotti_slides.ui.pages.new_mass.page import DATA, LITURGY, REVIEW, SONGS

from .conftest import FakeMassRepo
from .fakes import (
    LEAFLET_PDF,
    LYRICS,
    REPERTOIRE_URL,
    FakeGenerator,
    FakeResolver,
    FakeSongRepo,
    make_container,
    make_song,
)

SUNDAY = dt.date(2026, 10, 25)


@pytest.fixture
def container() -> Any:
    return make_container()


@pytest.fixture
def page(qtbot: QtBot, container: Any, tmp_path: Path) -> Iterator[NewMassPage]:
    widget = NewMassPage(NewMassService(container))
    qtbot.addWidget(widget)
    widget.resize(1100, 700)
    widget.show()
    widget.data_step.set_date(SUNDAY)
    widget.review_step.set_output_dir(tmp_path / "saida")
    yield widget


def idle(qtbot: QtBot, page: NewMassPage) -> None:
    qtbot.waitUntil(lambda: not page.is_busy(), timeout=15000)


def fill_liturgy(page: NewMassPage) -> None:
    fields = LiturgyFields(
        title="30° Domingo do Tempo Comum",
        first_reading="Ex 22,20-26",
        psalm_number="17(18)",
        psalm_refrain="Eu vos amo, Senhor.",
        gospel="Mt 22,34-40",
        intercessions_response="Senhor, escutai-nos.",
        eucharistic_prayer=EucharisticPrayer.III,
        mystery_of_faith="Anunciamos, Senhor, a vossa morte.",
    )
    page.liturgy_step.set_fields(fields)


def test_happy_path_without_leaflet(qtbot: QtBot, page: NewMassPage, container: Any) -> None:
    assert page.current_step() == DATA
    page.next_button.click()  # nothing to read: goes straight to the liturgy
    assert page.current_step() == LITURGY
    assert page.liturgy_step.prayers() == [EucharisticPrayer.II, EucharisticPrayer.III]
    fill_liturgy(page)
    page.next_button.click()
    assert page.current_step() == SONGS

    entrance = page.songs_step.cards[SongMoment.ENTRANCE]
    entrance.set_text("Eis-me aqui")
    entrance.search_button.click()
    assert page.is_busy()
    idle(qtbot, page)
    assert entrance.song() is not None
    assert "Do banco" in entrance.status()
    page.songs_step.cards[SongMoment.COMMUNION].set_text(LYRICS)  # not searched yet

    page.next_button.click()  # searches the pending card and moves on
    idle(qtbot, page)
    qtbot.waitUntil(lambda: page.current_step() == REVIEW, timeout=5000)
    assert page.songs_step.cards[SongMoment.COMMUNION].song() is not None
    assert page.review_step.generate_button.isEnabled()
    assert not page.review_step.is_blocked()

    page.review_step.generate_button.click()
    idle(qtbot, page)
    generator: FakeGenerator = container.generator
    assert len(generator.masses) == 1
    mass = generator.masses[0]
    assert mass.celebration.date == SUNDAY
    assert set(mass.songs) == {SongMoment.ENTRANCE, SongMoment.COMMUNION}
    assert page.review_step.result_visible()
    assert str(tmp_folder(page)) in page.review_step.pptx_label.text()
    assert page.review_step.open_button.isVisibleTo(page.review_step)
    qtbot.waitUntil(lambda: page.review_step.preview.page_count() > 0, timeout=5000)
    page.review_step.preview.render_all()
    assert page.review_step.preview.rendered_count() == page.review_step.preview.page_count()
    assert page.chat.messages()  # the chat followed the whole process


def tmp_folder(page: NewMassPage) -> Path:
    return page.review_step.output_dir()


def test_invalid_date_blocks_advance(page: NewMassPage) -> None:
    page.data_step.date_picker.reset()
    assert page.data_step.date() is None
    page.next_button.click()
    assert page.current_step() == DATA
    assert not page.data_step.date_error.isHidden()
    assert "Data inválida" in page.data_step.date_error.text()
    page.data_step.set_date(SUNDAY)
    page.next_button.click()
    assert page.current_step() == LITURGY


def test_date_defaults_to_next_sunday(qtbot: QtBot, container: Any) -> None:
    fresh = NewMassPage(NewMassService(container))
    qtbot.addWidget(fresh)
    picked = fresh.data_step.date()
    assert picked is not None
    assert picked.weekday() == 6
    assert picked >= dt.date.today()


def test_generate_disabled_with_blocking_error(qtbot: QtBot, page: NewMassPage) -> None:
    page.next_button.click()
    page.liturgy_step.set_fields(LiturgyFields(title="Só o título"))
    page.next_button.click()
    page.next_button.click()
    assert page.current_step() == REVIEW
    review = page.review_step
    assert review.is_blocked()
    assert not review.generate_button.isEnabled()
    levels = [level for level, _ in review.notice_messages()]
    assert "error" in levels
    # fixing the form unblocks it (review refreshes on change)
    fill_liturgy(page)
    assert review.generate_button.isEnabled()
    assert "error" not in [level for level, _ in review.notice_messages()]


def test_leaflet_marks_extracted_and_missing_fields(
    qtbot: QtBot, page: NewMassPage, container: Any
) -> None:
    page.data_step.drop_zone.set_path(LEAFLET_PDF, emit=True)
    page.next_button.click()
    idle(qtbot, page)
    qtbot.waitUntil(lambda: page.current_step() == LITURGY, timeout=5000)
    form = page.liturgy_step
    assert form.edits["gospel"].text() == "Mt 21,28-32"
    assert "extraído do folheto" in form.tag_text("gospel")
    assert "extraído do folheto" in form.tag_text("eucharistic_prayer")
    assert form.prayer() == EucharisticPrayer.III
    assert "não encontrado" in form.tag_text("mystery_of_faith")
    assert "não encontrado" in form.tag_text("intercessions_response")
    assert form.tag_text("short_title") == ""
    form.edits["mystery_of_faith"].setText("Anunciamos, Senhor.")
    assert form.tag_text("mystery_of_faith") == ""
    form.edits["gospel"].setText("Mt 22,1")  # edited by hand: no longer "as extracted"
    assert form.tag_text("gospel") == ""
    assert container.leaflet_extractor.calls == [LEAFLET_PDF]
    assert any("não foram encontrados" in text for text, _ in page.chat.messages())


def test_oe_list_only_has_template_prayers(page: NewMassPage) -> None:
    page.next_button.click()
    combo = page.liturgy_step.prayer_combo
    labels = [combo.itemText(i) for i in range(combo.count())]
    assert labels[1:] == ["OE II", "OE III"]


def test_gloria_switch_follows_season_until_touched(page: NewMassPage) -> None:
    form = page.liturgy_step
    assert form.has_gloria()

    def choose(season: LiturgicalSeason) -> None:
        for index in range(form.season_combo.count()):
            if form.season_combo.itemData(index) == season:
                form.season_combo.setCurrentIndex(index)

    choose(LiturgicalSeason.LENT)
    assert form.season() == LiturgicalSeason.LENT
    assert not form.has_gloria()
    form.set_has_gloria(True)  # solemnity: the user turns it on by hand
    choose(LiturgicalSeason.ADVENT)
    assert form.has_gloria()  # kept: it had been changed by hand
    form.set_has_gloria(False)
    choose(LiturgicalSeason.EASTER)  # not touched (matches the Advent rule): follows the season
    assert form.has_gloria()


def go_to_confirmation(qtbot: QtBot, page: NewMassPage) -> None:
    page.data_step.repertoire_edit.setText(REPERTOIRE_URL)
    page.next_button.click()
    idle(qtbot, page)
    qtbot.waitUntil(lambda: page.current_step() == LITURGY, timeout=5000)
    page.next_button.click()
    assert page.current_step() == SONGS


def test_repertoire_applies_only_after_confirmation(
    qtbot: QtBot, page: NewMassPage, container: Any
) -> None:
    go_to_confirmation(qtbot, page)
    songs = page.songs_step
    assert songs.is_confirming()
    confirm = songs.confirm
    assert len(confirm.rows()) == 7
    assert any(
        row.item.confidence == "low" and not row.low_label.isHidden() for row in confirm.rows()
    )
    # nothing is applied yet
    resolver: FakeResolver = container.resolver
    assert resolver.requests == []
    assert all(card.text() == "" and card.song() is None for card in songs.cards.values())

    rows = {row.item.title: row for row in confirm.rows()}
    # swap: "Eis-me Aqui" goes to the recessional, "Ave Maria" is ignored and freed up
    ave = rows["Ave Maria"]
    ave.combo.setCurrentText(IGNORE)
    eis = rows["Eis-me Aqui, Senhor"]
    eis.combo.setCurrentText(SongMoment.RECESSIONAL.label)
    assert confirm.conflicts() == []
    assert SongMoment.ENTRANCE in confirm.missing_moments()
    assert resolver.requests == []  # still nothing
    assert all(card.song() is None for card in songs.cards.values())

    confirm.confirm_button.click()
    idle(qtbot, page)
    assert not songs.is_confirming()
    assert songs.cards[SongMoment.RECESSIONAL].text().endswith("/eis-me-aqui-senhor/")
    assert songs.cards[SongMoment.RECESSIONAL].song() is not None
    assert songs.cards[SongMoment.ENTRANCE].text() == ""
    assert songs.cards[SongMoment.PENITENTIAL_ACT].song() is not None
    assert songs.cards[SongMoment.GLORIA].song() is not None
    assert len(resolver.requests) == 6  # seven songs minus the ignored one


def test_confirmation_blocks_two_songs_in_one_moment(qtbot: QtBot, page: NewMassPage) -> None:
    go_to_confirmation(qtbot, page)
    confirm = page.songs_step.confirm
    first, second = confirm.rows()[0], confirm.rows()[1]
    second.combo.setCurrentText(first.combo.currentText())
    assert confirm.conflicts()
    assert not confirm.confirm_button.isEnabled()
    assert not confirm.error_label.isHidden()


def test_cancelling_the_confirmation_fills_nothing(qtbot: QtBot, page: NewMassPage) -> None:
    go_to_confirmation(qtbot, page)
    page.songs_step.confirm.cancel_button.click()
    assert not page.songs_step.is_confirming()
    assert page.songs_step.songs() == {}
    assert all(card.text() == "" for card in page.songs_step.cards.values())


def test_cannot_leave_songs_while_confirming(qtbot: QtBot, page: NewMassPage) -> None:
    go_to_confirmation(qtbot, page)
    page.next_button.click()
    assert page.current_step() == SONGS


def test_candidates_are_chosen_by_the_user(qtbot: QtBot, page: NewMassPage, container: Any) -> None:
    page.next_button.click()
    page.next_button.click()
    card = page.songs_step.cards[SongMoment.OFFERTORY]
    card.set_text("ave")
    card.search_button.click()
    idle(qtbot, page)
    assert card.song() is None
    assert [c.title for c in card.candidates()] == ["Ave Maria", "Ave Maria (Gounod)"]
    assert any(kind == "question" for _, kind in page.chat.messages())
    card.candidate_buttons()[1].click()
    idle(qtbot, page)
    assert card.song() is not None
    assert card.song().title == "Ave Maria (Gounod)"  # type: ignore[union-attr]
    assert card.candidates() == []
    assert container.resolver.confirmed[0].song_id == 7


def test_edit_only_this_mass_does_not_touch_the_library(
    qtbot: QtBot, page: NewMassPage, container: Any
) -> None:
    card = page.songs_step.cards[SongMoment.ENTRANCE]
    card.set_song(make_song("Canto A"))
    edited = make_song("Canto A").model_copy(update={"title": "Canto A (ajustado)"})
    page.apply_edit(SongMoment.ENTRANCE, edited, "mass")
    repo: FakeSongRepo = container.song_repo
    assert repo.updated == [] and repo.added == []
    song = card.song()
    assert song is not None and song.title == "Canto A (ajustado)"
    page.apply_edit(SongMoment.ENTRANCE, edited, "library")
    assert len(repo.added) == 1  # the fake library has no such song, so it is added


def test_song_editor_edits_bold_type_and_order(qtbot: QtBot, page: NewMassPage) -> None:
    editor = SongEditor(make_song("Canto A"), page)
    qtbot.addWidget(editor)
    assert editor.order() == [2, 1, 2, 1]
    first = editor.stanza_editors[0]
    assert first.rows[0].bold.isChecked()
    first.rows[1].bold.setChecked(True)
    first.type_combo.setCurrentIndex(0)  # chorus -> verse
    first.add_line(Line(text="Nova linha"))
    first.rows[-1].edit.setText("Nova linha")
    editor.order_list.takeItem(3)
    editor.order_list.setCurrentRow(0)
    editor._repeat_selected()
    new_id = editor.add_stanza(editor.stanza_editors[0].stanza_type())
    editor.stanza_editors[-1].rows[0].edit.setText("Estrofe nova")
    song = editor.result_song()
    assert song.stanzas[0].type.value == "verse"
    assert [line.bold for line in song.stanzas[0].lines] == [True, True, False]
    assert song.order == [2, 1, 2, 2, new_id]
    editor.remove_stanza(2)
    assert 2 not in editor.result_song().order
    editor.save_to_library()
    assert editor.scope == "library"


def test_song_editor_needs_title_and_text(qtbot: QtBot, page: NewMassPage) -> None:
    editor = SongEditor(make_song("Canto A"), page)
    qtbot.addWidget(editor)
    assert editor.validate()
    editor.title_edit.setText(" ")
    assert not editor.validate()


def test_load_mass_reopens_and_duplicates(qtbot: QtBot, page: NewMassPage, container: Any) -> None:
    page.next_button.click()
    fill_liturgy(page)
    page.songs_step.cards[SongMoment.ENTRANCE].set_song(make_song("Entrada X"))
    mass, notices = page.current_mass()
    assert mass is not None and not [n for n in notices if n.level == "error"]
    page.reset()
    assert page.songs_step.songs() == {}

    page.load_mass(mass, duplicate=False)
    assert page.current_step() == REVIEW
    assert page.data_step.date() == SUNDAY
    assert page.songs_step.cards[SongMoment.ENTRANCE].song() is not None
    assert page.review_step.generate_button.isEnabled()

    page.load_mass(mass, duplicate=True)
    assert page.current_step() == DATA
    picked = page.data_step.date()
    assert picked is not None and picked.weekday() == 6
    assert page.liturgy_step.edits["gospel"].text() == "Mt 22,34-40"
    assert page.songs_step.cards[SongMoment.ENTRANCE].song() is not None


def test_leaflet_drop_zone_accepts_only_pdf(page: NewMassPage, tmp_path: Path) -> None:
    zone = page.data_step.drop_zone
    assert not zone.set_path(tmp_path / "folheto.docx")
    assert zone.path() is None and not zone.error_label.isHidden()
    assert zone.set_path(tmp_path / "folheto.pdf")
    assert zone.path() == tmp_path / "folheto.pdf"
    assert zone.error_label.isHidden()


def test_window_uses_the_real_page(qtbot: QtBot, container: Any, tmp_path: Path) -> None:
    from pallotti_slides.ui.pages.placeholder import PlaceholderPage

    container.mass_repo = FakeMassRepo()
    container.paths = SimpleNamespace(config=tmp_path / "config.json")
    window = MainWindow(container)
    qtbot.addWidget(window)
    assert isinstance(window.new_mass_page, NewMassPage)
    assert not isinstance(window.new_mass_page, PlaceholderPage)
    window.show_page(window.new_mass_page)
    assert window.current_page() is window.new_mass_page
    assert cast(NewMassPage, window.new_mass_page).data_step.date() is not None
    assert QDate.currentDate().isValid()
