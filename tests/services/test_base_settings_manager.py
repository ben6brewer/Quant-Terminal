"""Tests for app.services.base_settings_manager."""

import json

import pytest

from app.services.base_settings_manager import BaseSettingsManager, GenericSettingsManager


class TestGenericSettingsManager:
    @pytest.fixture
    def manager(self, tmp_path, monkeypatch):
        """GenericSettingsManager using temp directory."""
        monkeypatch.setattr(
            "pathlib.Path.home",
            lambda: tmp_path,
        )
        return GenericSettingsManager(
            "test_settings.json",
            {"color": "blue", "size": 10, "enabled": True},
        )

    def test_defaults(self, manager):
        assert manager.get_setting("color") == "blue"
        assert manager.get_setting("size") == 10
        assert manager.get_setting("enabled") is True

    def test_get_all_settings(self, manager):
        settings = manager.get_all_settings()
        assert settings == {"color": "blue", "size": 10, "enabled": True}

    def test_update_settings(self, manager):
        manager.update_settings({"color": "red"})
        assert manager.get_setting("color") == "red"
        # Other settings unchanged
        assert manager.get_setting("size") == 10

    def test_persistence(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        defaults = {"color": "blue", "size": 10}

        # Create, modify, and save
        m1 = GenericSettingsManager("test_settings.json", defaults)
        m1.update_settings({"color": "green"})

        # Create new instance - should load saved
        m2 = GenericSettingsManager("test_settings.json", defaults)
        assert m2.get_setting("color") == "green"

    def test_reset_to_defaults(self, manager):
        manager.update_settings({"color": "red", "size": 99})
        manager.reset_to_defaults()
        assert manager.get_setting("color") == "blue"
        assert manager.get_setting("size") == 10

    def test_has_custom_setting(self, manager):
        assert manager.has_custom_setting("color") is False
        manager.update_settings({"color": "red"})
        assert manager.has_custom_setting("color") is True

    def test_unknown_key_returns_none(self, manager):
        assert manager.get_setting("nonexistent") is None

    def test_stale_keys_dropped(self, tmp_path, monkeypatch):
        """Keys no longer in DEFAULT_SETTINGS should be dropped on load."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        # Save with extra key
        save_path = tmp_path / ".quant_terminal" / "test_settings.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump({"color": "red", "obsolete_key": "value"}, f)

        # Load with current defaults (no obsolete_key)
        m = GenericSettingsManager("test_settings.json", {"color": "blue", "size": 10})
        settings = m.get_all_settings()
        assert "obsolete_key" not in settings
        assert settings["color"] == "red"
        assert settings["size"] == 10  # New default added

    def test_corrupted_file_uses_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        save_path = tmp_path / ".quant_terminal" / "test_settings.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text("not valid json{{{")

        m = GenericSettingsManager("test_settings.json", {"color": "blue"})
        assert m.get_setting("color") == "blue"
