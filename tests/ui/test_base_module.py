"""Tests for app.ui.modules.base_module.BaseModule."""

import pytest

from app.ui.modules.base_module import BaseModule


@pytest.mark.ui
class TestBaseModule:
    @pytest.fixture
    def module(self, qapp, theme_manager):
        """Create a minimal BaseModule instance."""
        mod = BaseModule(theme_manager)
        return mod

    def test_instantiation(self, module):
        assert module is not None
        assert module.theme_manager is not None

    def test_show_loading(self, module):
        module.show()
        module._show_loading("Testing...")
        assert module._loading_overlay is not None
        assert module._loading_overlay.isVisible()

    def test_hide_loading(self, module):
        module.show()
        module._show_loading("Testing...")
        module._hide_loading()
        assert not module._loading_overlay.isVisible()

    def test_cancel_worker_no_error(self, module):
        """cancel_worker should not raise when no worker is running."""
        module._cancel_worker()

    def test_home_clicked_signal(self, module, qtbot):
        """home_clicked signal should be emittable."""
        with qtbot.waitSignal(module.home_clicked, timeout=1000):
            module.home_clicked.emit()

    def test_run_worker(self, module, qtbot):
        """_run_worker should start a background computation."""
        results = []

        def on_complete(result):
            results.append(result)

        module._run_worker(
            lambda: 42,
            loading_message="Computing...",
            on_complete=on_complete,
        )
        # Wait for worker to finish
        qtbot.waitUntil(lambda: len(results) > 0, timeout=5000)
        assert results[0] == 42

    def test_run_worker_error(self, module, qtbot):
        """_run_worker should handle errors."""
        errors = []

        def on_error(msg):
            errors.append(msg)

        module._run_worker(
            lambda: 1 / 0,
            loading_message="Failing...",
            on_error=on_error,
        )
        qtbot.waitUntil(lambda: len(errors) > 0, timeout=5000)
        assert "division" in errors[0].lower()
