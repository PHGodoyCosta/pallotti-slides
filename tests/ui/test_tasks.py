from PySide6.QtCore import QThread
from pytestqt.qtbot import QtBot

from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.ui.tasks import ProgressCallback, Task, start_task


def test_task_emits_progress_and_finished(qtbot: QtBot) -> None:
    def work(report: ProgressCallback) -> object:
        report("passo 1")
        return QThread.currentThread()

    task = Task(work)
    steps: list[str] = []
    task.signals.progress.connect(steps.append)
    with qtbot.waitSignal(task.signals.finished, timeout=3000) as blocker:
        start_task(task)
    assert steps == ["passo 1"]
    assert blocker.args is not None
    assert blocker.args[0] is not QThread.currentThread()  # ran off the UI thread


def test_task_failure_uses_error_message(qtbot: QtBot) -> None:
    def work(report: ProgressCallback) -> object:
        raise PallottiError("deu ruim")

    task = Task(work)
    with qtbot.waitSignal(task.signals.failed, timeout=3000) as blocker:
        start_task(task)
    assert blocker.args == ["deu ruim"]


def test_task_unexpected_error_fails_too(qtbot: QtBot) -> None:
    def work(report: ProgressCallback) -> object:
        raise RuntimeError("x")

    task = Task(work)
    with qtbot.waitSignal(task.signals.failed, timeout=3000):
        start_task(task)
