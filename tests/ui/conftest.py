import os
from collections.abc import Iterator
from typing import cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pallotti_slides.application.container import Container
from pallotti_slides.ui.main_window import MainWindow


class FakeContainer:
    """Stands in for ``Container``; the shell only needs ``close``."""

    closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def window(qtbot) -> Iterator[MainWindow]:  # type: ignore[no-untyped-def]
    win = MainWindow(cast(Container, FakeContainer()))
    qtbot.addWidget(win)
    win.show()
    yield win
