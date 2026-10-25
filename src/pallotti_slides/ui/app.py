"""Entry point of the graphical interface."""

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication, QMessageBox

from pallotti_slides.application.container import Container, create_container
from pallotti_slides.config import load_settings
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.ui.main_window import MainWindow
from pallotti_slides.ui.theme import DEFAULT_ACCENT, apply_theme


def main(argv: Sequence[str] | None = None) -> int:
    """Open the main window and run the event loop."""
    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName("Pallotti Slides")
    settings = load_settings()
    # Settings has no theme field yet (arrives with the Settings page, M9d).
    apply_theme(getattr(settings, "theme", "system"), DEFAULT_ACCENT)
    container: Container
    try:
        container = create_container(settings)
    except PallottiError as error:
        QMessageBox.critical(None, "Pallotti Slides", str(error))
        return 1
    window = MainWindow(container)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
