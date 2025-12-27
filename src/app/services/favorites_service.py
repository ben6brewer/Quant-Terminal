from __future__ import annotations

import json
from pathlib import Path
from typing import List, Set


class FavoritesService:
    """
    Service for managing favorite modules.
    Persists favorites to disk for cross-session persistence.
    """

    # Storage for favorited module IDs
    _favorites: Set[str] = set()

    # Path to save/load favorites
    _SAVE_PATH = Path.home() / ".quant_terminal" / "favorites.json"

    @classmethod
    def initialize(cls) -> None:
        """Initialize the service and load saved favorites."""
        cls.load_favorites()

    @classmethod
    def load_favorites(cls) -> None:
        """Load favorites from disk."""
        if not cls._SAVE_PATH.exists():
            cls._favorites = set()
            return

        try:
            with open(cls._SAVE_PATH, "r") as f:
                data = json.load(f)
                cls._favorites = set(data.get("favorites", []))
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading favorites: {e}")
            cls._favorites = set()

    @classmethod
    def save_favorites(cls) -> None:
        """Save favorites to disk."""
        # Ensure directory exists
        cls._SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(cls._SAVE_PATH, "w") as f:
                json.dump({"favorites": list(cls._favorites)}, f, indent=2)
        except IOError as e:
            print(f"Error saving favorites: {e}")

    @classmethod
    def is_favorite(cls, module_id: str) -> bool:
        """Check if a module is favorited."""
        return module_id in cls._favorites

    @classmethod
    def toggle_favorite(cls, module_id: str) -> bool:
        """
        Toggle favorite status for a module.
        Returns the new favorite status (True if now favorited, False if unfavorited).
        """
        if module_id in cls._favorites:
            cls._favorites.remove(module_id)
            is_favorite = False
        else:
            cls._favorites.add(module_id)
            is_favorite = True

        # Auto-save on every toggle
        cls.save_favorites()
        return is_favorite

    @classmethod
    def get_favorites(cls) -> List[str]:
        """Get list of all favorited module IDs."""
        return list(cls._favorites)
