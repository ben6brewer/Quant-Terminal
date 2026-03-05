"""Tests for app.ui.widgets.common.loading_overlay.LoadingOverlay."""

import pytest

from PySide6.QtWidgets import QWidget


@pytest.mark.ui
class TestLoadingOverlay:
    @pytest.fixture
    def overlay(self, qapp, theme_manager):
        from app.ui.widgets.common.loading_overlay import LoadingOverlay

        parent = QWidget()
        parent.resize(400, 300)
        ov = LoadingOverlay(parent, theme_manager)
        ov._test_parent = parent  # prevent GC of parent
        return ov

    def test_instantiation(self, overlay):
        assert overlay is not None

    def test_set_message(self, overlay):
        overlay.set_message("Loading data...")
        assert overlay._message == "Loading data..."

    def test_set_progress(self, overlay):
        overlay.set_progress(50, 100, "Fetching")
        assert "50" in overlay._message or "Fetching" in overlay._message

    def test_show_hide(self, overlay):
        overlay._test_parent.show()
        overlay.show()
        assert overlay.isVisible()
        overlay.hide()
        assert not overlay.isVisible()

    def test_stop(self, overlay):
        overlay.show()
        overlay.stop()
        # Should not raise
