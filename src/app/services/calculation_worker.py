"""Generic background worker for running calculations off the main thread."""

from PySide6.QtCore import QObject, Signal


class CalculationWorker(QObject):
    """Generic worker that runs a callable in a background QThread.

    Usage:
        worker = CalculationWorker(some_service.method, arg1, arg2, key=val)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_complete)
        worker.error.connect(on_error)
        thread.start()
    """

    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
