"""Tests for app.services.preferences_service.PreferencesService."""

import pytest

from app.services.preferences_service import PreferencesService


class TestPreferencesService:
    @pytest.fixture(autouse=True)
    def reset(self, tmp_path, monkeypatch):
        PreferencesService._preferences = {}
        monkeypatch.setattr(PreferencesService, "_SAVE_PATH", tmp_path / "preferences.json")
        yield
        PreferencesService._preferences = {}

    def test_default_theme(self):
        PreferencesService.initialize()
        assert PreferencesService.get_theme() == "bloomberg"

    def test_set_theme(self):
        PreferencesService.initialize()
        PreferencesService.set_theme("dark")
        assert PreferencesService.get_theme() == "dark"

    def test_generic_get_set(self):
        PreferencesService.initialize()
        PreferencesService.set("custom_key", "custom_value")
        assert PreferencesService.get("custom_key") == "custom_value"

    def test_get_default(self):
        PreferencesService.initialize()
        assert PreferencesService.get("nonexistent", "fallback") == "fallback"

    def test_persistence(self, tmp_path, monkeypatch):
        monkeypatch.setattr(PreferencesService, "_SAVE_PATH", tmp_path / "prefs.json")
        PreferencesService.initialize()
        PreferencesService.set_theme("light")
        PreferencesService.save_preferences()

        # Reload
        PreferencesService._preferences = {}
        PreferencesService.load_preferences()
        assert PreferencesService.get_theme() == "light"
