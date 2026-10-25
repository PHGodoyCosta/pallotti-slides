"""Background execution: the interface never blocks on long operations."""

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from pallotti_slides.domain.errors import PallottiError

ProgressCallback = Callable[[str], None]


class TaskSignals(QObject):
    """Signals of a ``Task`` (a QRunnable cannot have its own)."""

    finished = Signal(object)  # the function's result
    failed = Signal(str)  # message in Portuguese for the user
    progress = Signal(str)


class Task(QRunnable):
    """Runs ``function(report)`` in a worker thread.

    ``report(text)`` emits ``signals.progress``. A ``PallottiError`` becomes ``failed`` with its
    message; any other exception gets a generic message (details go to the log, not the UI).
    """

    def __init__(self, function: Callable[[ProgressCallback], object]) -> None:
        super().__init__()
        self.setAutoDelete(False)  # the signals object must outlive the run
        self._function = function
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            result = self._function(self.signals.progress.emit)
        except PallottiError as error:
            self.signals.failed.emit(str(error))
        except Exception as error:
            self.signals.failed.emit(f"Erro inesperado: {error}")
        else:
            self.signals.finished.emit(result)


def start_task(task: Task, pool: QThreadPool | None = None) -> Task:
    """Queue ``task`` in ``pool`` (default: the global pool) and return it."""
    (pool or QThreadPool.globalInstance()).start(task)
    return task
