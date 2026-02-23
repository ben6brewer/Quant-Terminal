"""Base Settings Manager - Abstract base class for module-specific settings."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Dict, Any


class BaseSettingsManager(ABC):
    """
    Abstract base class for module settings with persistent storage.

    Subclasses must define:
    - DEFAULT_SETTINGS: Dict of default setting values
    - settings_filename: Filename for settings JSON (e.g., 'chart_settings.json')

    The base class provides:
    - Automatic loading/saving to ~/.quant_terminal/{settings_filename}
    - Common get/set/reset operations
    - Hooks for serialization/deserialization of special types
    """

    @property
    @abstractmethod
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        """Default settings dict (must be overridden)."""
        pass

    @property
    @abstractmethod
    def settings_filename(self) -> str:
        """Filename for settings JSON (e.g., 'chart_settings.json')."""
        pass

    def __init__(self):
        self._settings = self.DEFAULT_SETTINGS.copy()
        self._save_path = Path.home() / ".quant_terminal" / self.settings_filename
        self.load_settings()

    def get_setting(self, key: str) -> Any:
        """Get a specific setting value."""
        return self._settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings.copy()

    def update_settings(self, settings: Dict[str, Any]) -> None:
        """Update settings and save to disk."""
        self._settings.update(settings)
        self.save_settings()

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = self.DEFAULT_SETTINGS.copy()
        self.save_settings()

    def save_settings(self) -> None:
        """Save settings to disk."""
        try:
            self._save_path.parent.mkdir(parents=True, exist_ok=True)
            serialized = self._serialize_settings(self._settings)
            with open(self._save_path, 'w') as f:
                json.dump(serialized, f, indent=2)
        except Exception as e:
            print(f"Error saving settings to {self._save_path}: {e}")

    def load_settings(self) -> None:
        """Load settings from disk, merging with current defaults.

        New default keys are automatically added; stale keys that no
        longer appear in ``DEFAULT_SETTINGS`` are dropped.
        """
        try:
            if not self._save_path.exists():
                return
            with open(self._save_path, 'r') as f:
                data = json.load(f)
            deserialized = self._deserialize_settings(data)
            # Start from defaults, overlay only recognised saved keys
            merged = self.DEFAULT_SETTINGS.copy()
            for key in merged:
                if key in deserialized:
                    merged[key] = deserialized[key]
            self._settings = merged
        except Exception as e:
            print(f"Error loading settings from {self._save_path}: {e}")
            self._settings = self.DEFAULT_SETTINGS.copy()

    def has_custom_setting(self, key: str) -> bool:
        """Check if a setting has been customized (differs from default)."""
        return self._settings.get(key) != self.DEFAULT_SETTINGS.get(key)

    def _serialize_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert settings to JSON-serializable format.

        Override in subclasses to handle special types (e.g., Qt.PenStyle, tuples).
        Default implementation returns a shallow copy.
        """
        return settings.copy()

    def _deserialize_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert settings from JSON format to runtime format.

        Override in subclasses to handle special types (e.g., Qt.PenStyle, tuples).
        Default implementation returns a shallow copy.
        """
        return data.copy()
