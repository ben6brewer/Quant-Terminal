from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class PreferencesService:
    """
    Service for managing user preferences.
    Persists preferences to disk for cross-session persistence.
    """

    # Path to save/load preferences
    _SAVE_PATH = Path.home() / ".quant_terminal" / "preferences.json"

    # Default preferences
    _DEFAULT_PREFERENCES = {
        "theme": "bloomberg"  # Default theme
    }

    # In-memory preferences
    _preferences = {}

    @classmethod
    def initialize(cls) -> None:
        """Initialize the service and load saved preferences."""
        cls.load_preferences()

    @classmethod
    def load_preferences(cls) -> None:
        """Load preferences from disk."""
        if not cls._SAVE_PATH.exists():
            cls._preferences = cls._DEFAULT_PREFERENCES.copy()
            return

        try:
            with open(cls._SAVE_PATH, "r") as f:
                data = json.load(f)
                cls._preferences = {**cls._DEFAULT_PREFERENCES, **data}
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading preferences: {e}")
            cls._preferences = cls._DEFAULT_PREFERENCES.copy()

    @classmethod
    def save_preferences(cls) -> None:
        """Save preferences to disk."""
        # Ensure directory exists
        cls._SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(cls._SAVE_PATH, "w") as f:
                json.dump(cls._preferences, f, indent=2)
        except IOError as e:
            print(f"Error saving preferences: {e}")

    @classmethod
    def get_theme(cls) -> str:
        """Get the saved theme preference."""
        return cls._preferences.get("theme", "bloomberg")

    @classmethod
    def set_theme(cls, theme: str) -> None:
        """
        Set the theme preference and save to disk.

        Args:
            theme: Theme name (dark, light, or bloomberg)
        """
        cls._preferences["theme"] = theme
        cls.save_preferences()

    @classmethod
    def get(cls, key: str, default=None):
        """Get a preference value by key."""
        return cls._preferences.get(key, default)

    @classmethod
    def set(cls, key: str, value) -> None:
        """Set a preference value and save to disk."""
        cls._preferences[key] = value
        cls.save_preferences()
