import pytest
from qfluentwidgets import isDarkTheme

from pallotti_slides import __version__
from pallotti_slides.ui.main_window import MainWindow
from pallotti_slides.ui.theme import apply_theme


def test_window_opens_on_home(window: MainWindow) -> None:
    assert window.isVisible()
    assert window.current_page() is window.home_page


def test_navigation_switches_page(window: MainWindow) -> None:
    for page in (
        window.new_mass_page,
        window.library_page,
        window.history_page,
        window.settings_page,
        window.about_page,
    ):
        window.show_page(page)
        assert window.current_page() is page


def test_home_shortcuts(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.home_page.new_mass_button.click()
    assert window.current_page() is window.new_mass_page
    window.show_page(window.home_page)
    window.home_page.history_button.click()
    assert window.current_page() is window.history_page


def test_about_shows_version(window: MainWindow) -> None:
    assert __version__ in window.about_page.version_label.text()


def test_theme_toggles(window: MainWindow) -> None:
    apply_theme("dark")
    assert isDarkTheme()
    apply_theme("light")
    assert not isDarkTheme()
    with pytest.raises(ValueError):
        apply_theme("sepia")
