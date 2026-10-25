"""Main window: side navigation and pages."""

from typing import cast

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition

from pallotti_slides.application.container import Container
from pallotti_slides.application.library import SongLibrary
from pallotti_slides.application.mass_history import MassHistory
from pallotti_slides.application.new_mass import NewMassService
from pallotti_slides.application.settings_service import SettingsService
from pallotti_slides.domain.models import Mass
from pallotti_slides.ui.assets import image_path
from pallotti_slides.ui.pages.about import AboutPage
from pallotti_slides.ui.pages.history import HistoryPage
from pallotti_slides.ui.pages.home import HomePage
from pallotti_slides.ui.pages.library import LibraryPage
from pallotti_slides.ui.pages.new_mass import NewMassPage
from pallotti_slides.ui.pages.settings import SettingsPage


class MainWindow(FluentWindow):  # type: ignore[misc]
    """Início, Nova Missa, Biblioteca, Histórico; Configurações and Sobre at the bottom."""

    def __init__(
        self,
        container: Container,
        parent: QWidget | None = None,
        settings_service: SettingsService | None = None,
    ) -> None:
        super().__init__(parent)
        self.container = container
        self.setWindowTitle("Pallotti Slides")
        self.setWindowIcon(QIcon(str(image_path("icon.png"))))
        self.resize(1100, 720)
        self.setMinimumSize(820, 560)

        self.home_page = HomePage()
        self.new_mass_page = NewMassPage(NewMassService(container))
        self.library_page = LibraryPage(SongLibrary.from_container(container))
        self.history_page = HistoryPage(MassHistory(container.mass_repo))
        self.settings_page = SettingsPage(
            settings_service or SettingsService(container.paths.config)
        )
        self.about_page = AboutPage()

        self.addSubInterface(self.home_page, FluentIcon.HOME, "Início")
        self.addSubInterface(self.new_mass_page, FluentIcon.ADD, "Nova Missa")
        self.addSubInterface(self.library_page, FluentIcon.LIBRARY, "Biblioteca")
        self.addSubInterface(self.history_page, FluentIcon.HISTORY, "Histórico")
        self.addSubInterface(
            self.settings_page, FluentIcon.SETTING, "Configurações", NavigationItemPosition.BOTTOM
        )
        self.addSubInterface(
            self.about_page, FluentIcon.INFO, "Sobre", NavigationItemPosition.BOTTOM
        )

        self.home_page.new_mass_requested.connect(lambda: self.show_page(self.new_mass_page))
        self.home_page.history_requested.connect(lambda: self.show_page(self.history_page))
        self.history_page.mass_requested.connect(self._load_mass)

    def _load_mass(self, mass: Mass, duplicate: bool) -> None:
        """Hand a Mass from the history to the Nova Missa page."""
        self.new_mass_page.load_mass(mass, duplicate)
        self.show_page(self.new_mass_page)

    def show_page(self, page: QWidget) -> None:
        """Switch to ``page`` (keeps the navigation highlight in sync)."""
        self.switchTo(page)

    def current_page(self) -> QWidget:
        """The page currently shown."""
        return cast(QWidget, self.stackedWidget.currentWidget())

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.container.close()
        super().closeEvent(event)
