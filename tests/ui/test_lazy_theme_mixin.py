"""Tests for app.ui.widgets.common.lazy_theme_mixin.LazyThemeMixin."""

from unittest.mock import MagicMock

import pytest


@pytest.mark.ui
class TestLazyThemeMixin:
    def test_dirty_flag_mechanism(self, qapp):
        from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
        from PySide6.QtWidgets import QWidget

        class TestWidget(LazyThemeMixin, QWidget):
            def __init__(self):
                QWidget.__init__(self)
                self._theme_dirty = False
                self._apply_theme_called = False

            def _apply_theme(self):
                self._apply_theme_called = True

        widget = TestWidget()

        # When hidden, theme change should mark dirty
        widget.hide()
        widget._on_theme_changed_lazy()
        assert widget._theme_dirty is True
        assert widget._apply_theme_called is False

        # When checked on show, should apply and clear dirty
        widget._check_theme_dirty()
        assert widget._apply_theme_called is True
        assert widget._theme_dirty is False

    def test_visible_applies_immediately(self, qapp):
        from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
        from PySide6.QtWidgets import QWidget

        class TestWidget(LazyThemeMixin, QWidget):
            def __init__(self):
                QWidget.__init__(self)
                self._theme_dirty = False
                self._apply_theme_called = False

            def _apply_theme(self):
                self._apply_theme_called = True

        widget = TestWidget()
        widget.show()
        widget._on_theme_changed_lazy()
        assert widget._apply_theme_called is True
