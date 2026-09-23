"""Tests for app.services.calculation_worker.CalculationWorker.

The worker deliberately no longer emits its legacy ``finished``/``error``
signals from ``run()`` (cross-thread emission raced with widget construction);
callers read ``worker.result`` / ``worker.error_msg`` after ``QThread.finished``.

``run()`` ends with ``self.thread().quit()``.  Calling it directly on a worker
that still lives in the MAIN thread would quit the main thread's event loop
and break later Qt tests (queued slots never run), so :func:`_make` parks each
worker on an unstarted QThread first.
"""

from PySide6.QtCore import QThread

from app.services.calculation_worker import CalculationWorker

_parking = []  # keep the unstarted QThreads alive for the session


def _make(fn, *args, **kwargs) -> CalculationWorker:
    worker = CalculationWorker(fn, *args, **kwargs)
    thread = QThread()
    worker.moveToThread(thread)
    _parking.append((thread, worker))
    return worker


class TestCalculationWorker:
    def test_success(self):
        """run() stores the callable's return value."""
        worker = _make(lambda: 42)
        worker.run()

        assert worker.result == 42
        assert worker.error_msg is None

    def test_error(self):
        """run() stores the exception message instead of raising."""

        def failing_fn():
            raise ValueError("test error")

        worker = _make(failing_fn)
        worker.run()

        assert worker.result is None
        assert "test error" in worker.error_msg

    def test_with_args(self):
        worker = _make(lambda a, b: a + b, 3, 4)
        worker.run()
        assert worker.result == 7

    def test_with_kwargs(self):
        worker = _make(lambda x=0, y=0: x * y, x=5, y=6)
        worker.run()
        assert worker.result == 30

    def test_returns_complex_result(self):
        worker = _make(lambda: {"data": [1, 2, 3], "status": "ok"})
        worker.run()
        assert worker.result["status"] == "ok"

    def test_run_does_not_emit_legacy_signals(self):
        """Signals must not fire from run() (thread-safety contract)."""
        emitted = []
        worker = _make(lambda: 1)
        worker.finished.connect(emitted.append)
        worker.error.connect(emitted.append)
        worker.run()
        assert emitted == []
