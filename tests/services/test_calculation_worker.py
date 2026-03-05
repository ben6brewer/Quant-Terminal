"""Tests for app.services.calculation_worker.CalculationWorker."""

import pytest

from app.services.calculation_worker import CalculationWorker


class TestCalculationWorker:
    def test_success(self):
        """Worker should emit finished signal with result."""
        results = []
        errors = []

        def on_finish(result):
            results.append(result)

        def on_error(msg):
            errors.append(msg)

        worker = CalculationWorker(lambda: 42)
        worker.finished.connect(on_finish)
        worker.error.connect(on_error)
        worker.run()

        assert results == [42]
        assert errors == []

    def test_error(self):
        """Worker should emit error signal on exception."""
        results = []
        errors = []

        def on_finish(result):
            results.append(result)

        def on_error(msg):
            errors.append(msg)

        def failing_fn():
            raise ValueError("test error")

        worker = CalculationWorker(failing_fn)
        worker.finished.connect(on_finish)
        worker.error.connect(on_error)
        worker.run()

        assert results == []
        assert len(errors) == 1
        assert "test error" in errors[0]

    def test_with_args(self):
        results = []
        worker = CalculationWorker(lambda a, b: a + b, 3, 4)
        worker.finished.connect(results.append)
        worker.run()
        assert results == [7]

    def test_with_kwargs(self):
        results = []
        worker = CalculationWorker(lambda x=0, y=0: x * y, x=5, y=6)
        worker.finished.connect(results.append)
        worker.run()
        assert results == [30]

    def test_returns_complex_result(self):
        results = []
        worker = CalculationWorker(lambda: {"data": [1, 2, 3], "status": "ok"})
        worker.finished.connect(results.append)
        worker.run()
        assert results[0]["status"] == "ok"
