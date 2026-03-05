"""Tests for app.core.theme_manager.ThemeManager."""

import pytest


@pytest.mark.ui
class TestThemeManager:
    def test_default_theme(self, theme_manager):
        assert theme_manager.current_theme == "bloomberg"

    def test_set_theme(self, theme_manager):
        theme_manager.set_theme("dark", save_preference=False)
        assert theme_manager.current_theme == "dark"

    def test_invalid_theme_raises(self, theme_manager):
        with pytest.raises(ValueError, match="Unknown theme"):
            theme_manager.set_theme("invalid_theme", save_preference=False)

    def test_theme_changed_signal(self, theme_manager, qtbot):
        with qtbot.waitSignal(theme_manager.theme_changed, timeout=1000):
            theme_manager.set_theme("light", save_preference=False)

    def test_register_listener(self, theme_manager):
        results = []
        theme_manager.register_listener(results.append)
        theme_manager.set_theme("dark", save_preference=False)
        assert "dark" in results

    def test_unregister_listener(self, theme_manager):
        results = []
        callback = results.append
        theme_manager.register_listener(callback)
        theme_manager.unregister_listener(callback)
        theme_manager.set_theme("dark", save_preference=False)
        assert len(results) == 0
