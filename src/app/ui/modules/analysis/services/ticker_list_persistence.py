"""Ticker List Persistence - Save/load named ticker lists to disk."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class TickerListPersistence:
    """Persist named ticker lists as JSON files.

    Storage: ~/.quant_terminal/ticker_lists/{name}.json
    Format: {"name": "...", "created_date": "...", "tickers": [...]}
    """

    _LISTS_DIR = Path.home() / ".quant_terminal" / "ticker_lists"

    @classmethod
    def list_all(cls) -> List[str]:
        """List all saved ticker list names (sorted alphabetically)."""
        if not cls._LISTS_DIR.exists():
            return []
        return sorted(p.stem for p in cls._LISTS_DIR.glob("*.json"))

    @classmethod
    def load_list(cls, name: str) -> Optional[List[str]]:
        """Load tickers from a saved list.

        Returns:
            List of ticker strings, or None if not found.
        """
        path = cls._LISTS_DIR / f"{name}.json"
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("tickers", [])
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading ticker list {name}: {e}")
            return None

    @classmethod
    def save_list(cls, name: str, tickers: List[str]) -> bool:
        """Save tickers to a named list (creates or overwrites).

        Returns:
            True on success, False on error.
        """
        try:
            cls._LISTS_DIR.mkdir(parents=True, exist_ok=True)
            path = cls._LISTS_DIR / f"{name}.json"

            data = {
                "name": name,
                "created_date": datetime.now().isoformat(),
                "tickers": list(tickers),
            }

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving ticker list {name}: {e}")
            return False

    @classmethod
    def clear_all(cls) -> None:
        """Delete all saved ticker lists."""
        if not cls._LISTS_DIR.exists():
            return
        for f in cls._LISTS_DIR.glob("*.json"):
            f.unlink()

    @classmethod
    def delete_list(cls, name: str) -> bool:
        """Delete a saved ticker list.

        Returns:
            True on success, False if not found or error.
        """
        path = cls._LISTS_DIR / f"{name}.json"
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except OSError as e:
            print(f"Error deleting ticker list {name}: {e}")
            return False
