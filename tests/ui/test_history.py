import datetime as dt
from pathlib import Path
from typing import cast

from pallotti_slides.application.container import Container
from pallotti_slides.application.mass_history import MassSummary
from pallotti_slides.domain.enums import EucharisticPrayer, LiturgicalSeason
from pallotti_slides.domain.models import Celebration, Liturgy, Mass
from pallotti_slides.ui.main_window import MainWindow
from pallotti_slides.ui.pages.history import HistoryPage

from .conftest import FakeContainer, FakeMassRepo, make_service


def _mass() -> Mass:
    return Mass(
        celebration=Celebration(
            title="26° Domingo do Tempo Comum",
            date=dt.date(2026, 9, 26),
            season=LiturgicalSeason.ORDINARY_TIME,
        ),
        liturgy=Liturgy(
            first_reading="a",
            psalm_number="1",
            psalm_refrain="r",
            gospel="g",
            intercessions_response="i",
            eucharistic_prayer=EucharisticPrayer.III,
            mystery_of_faith="m",
        ),
        has_gloria=True,
        songs={},
    )


def _repo(tmp_path: Path) -> FakeMassRepo:
    summary = MassSummary(
        id=7,
        date=dt.date(2026, 9, 26),
        title="26° Domingo do Tempo Comum",
        eucharistic_prayer=EucharisticPrayer.III,
        pptx_path=tmp_path / "missa.pptx",
        pdf_path=tmp_path / "missa.pdf",
        created_at=dt.datetime(2026, 9, 20, 10, 0),
    )
    repo = FakeMassRepo([summary])
    repo.masses[7] = _mass()
    return repo


def test_lists_masses_and_emits_signal(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    page = HistoryPage(_repo(tmp_path))  # type: ignore[arg-type]
    qtbot.addWidget(page)
    assert len(page.rows) == 1
    assert not page.empty_label.isVisibleTo(page)
    assert page.rows[0].summary.title.startswith("26°")
    assert "missa.pptx" in page.rows[0].files_label.text()

    with qtbot.waitSignal(page.mass_requested) as reopen:
        page.rows[0].reopen_button.click()
    assert reopen.args[1] is False
    assert reopen.args[0].celebration.date == dt.date(2026, 9, 26)
    with qtbot.waitSignal(page.mass_requested) as duplicate:
        page.rows[0].duplicate_button.click()
    assert duplicate.args[1] is True


def test_empty_history(qtbot) -> None:  # type: ignore[no-untyped-def]
    page = HistoryPage(FakeMassRepo())  # type: ignore[arg-type]
    qtbot.addWidget(page)
    page.show()
    assert page.rows == []
    assert page.empty_label.isVisible()


def test_window_hands_mass_to_new_mass_page(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    container = FakeContainer()
    container.mass_repo = _repo(tmp_path)
    window = MainWindow(
        cast(Container, container), settings_service=make_service(tmp_path / "c.json")
    )
    qtbot.addWidget(window)
    received: list[tuple[Mass, bool]] = []
    window.new_mass_page.load_mass = lambda mass, dup: received.append((mass, dup))  # type: ignore[attr-defined]
    window.history_page.refresh()
    window.history_page.rows[0].duplicate_button.click()
    assert received and received[0][1] is True
    assert window.current_page() is window.new_mass_page
