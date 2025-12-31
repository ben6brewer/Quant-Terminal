"""Portfolio Persistence Service - Save/Load Portfolio JSON Files"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class PortfolioPersistence:
    """
    Singleton service for saving/loading portfolio JSON files.
    Handles all file I/O operations for portfolios.
    """

    _PORTFOLIOS_DIR = Path.home() / ".quant_terminal" / "portfolios"
    _RECENT_FILE = Path.home() / ".quant_terminal" / "recent_portfolios.json"
    _DEFAULT_PORTFOLIO = "Default"

    @classmethod
    def initialize(cls) -> None:
        """Create portfolios directory if it doesn't exist."""
        cls._PORTFOLIOS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def list_portfolios(cls) -> List[str]:
        """
        List all available portfolio names (without .json extension).

        Returns:
            List of portfolio names
        """
        if not cls._PORTFOLIOS_DIR.exists():
            return []
        return [p.stem for p in cls._PORTFOLIOS_DIR.glob("*.json")]

    @classmethod
    def load_portfolio(cls, name: str) -> Optional[Dict[str, Any]]:
        """
        Load portfolio by name.

        Args:
            name: Portfolio name (without .json extension)

        Returns:
            Portfolio dict or None if not found
        """
        path = cls._PORTFOLIOS_DIR / f"{name}.json"
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                portfolio = json.load(f)

            # Migrate: Add sequence numbers if missing (for same-day ordering)
            transactions = portfolio.get("transactions", [])
            needs_save = False
            for i, tx in enumerate(transactions):
                if "sequence" not in tx:
                    tx["sequence"] = i  # Assign based on array position
                    needs_save = True

            # Auto-save migrated portfolio
            if needs_save:
                cls.save_portfolio(portfolio)

            return portfolio
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading portfolio {name}: {e}")
            return None

    @classmethod
    def save_portfolio(cls, portfolio: Dict[str, Any]) -> bool:
        """
        Save portfolio to disk.

        Args:
            portfolio: Portfolio dict with "name" and "transactions"

        Returns:
            True if saved successfully, False otherwise
        """
        name = portfolio.get("name", cls._DEFAULT_PORTFOLIO)
        path = cls._PORTFOLIOS_DIR / f"{name}.json"

        try:
            # Update last_modified timestamp
            portfolio["last_modified"] = datetime.now().isoformat()

            # Ensure directory exists
            cls._PORTFOLIOS_DIR.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(portfolio, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving portfolio {name}: {e}")
            return False

    @classmethod
    def delete_portfolio(cls, name: str) -> bool:
        """
        Delete portfolio file.

        Args:
            name: Portfolio name to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        path = cls._PORTFOLIOS_DIR / f"{name}.json"
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError as e:
                print(f"Error deleting portfolio {name}: {e}")
                return False
        return False

    @classmethod
    def create_new_portfolio(cls, name: str) -> Dict[str, Any]:
        """
        Create a new empty portfolio.

        Args:
            name: Portfolio name

        Returns:
            New portfolio dict
        """
        return {
            "name": name,
            "created_date": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "transactions": []
        }

    @classmethod
    def portfolio_exists(cls, name: str) -> bool:
        """
        Check if portfolio exists.

        Args:
            name: Portfolio name

        Returns:
            True if portfolio file exists, False otherwise
        """
        path = cls._PORTFOLIOS_DIR / f"{name}.json"
        return path.exists()

    @classmethod
    def rename_portfolio(cls, old_name: str, new_name: str) -> bool:
        """
        Rename a portfolio.

        Args:
            old_name: Current portfolio name
            new_name: New portfolio name

        Returns:
            True if renamed successfully, False otherwise
        """
        if old_name == new_name:
            return True  # No change needed

        old_path = cls._PORTFOLIOS_DIR / f"{old_name}.json"
        new_path = cls._PORTFOLIOS_DIR / f"{new_name}.json"

        if not old_path.exists():
            return False

        if new_path.exists():
            return False  # Target name already exists

        try:
            # Load portfolio
            with open(old_path, "r", encoding="utf-8") as f:
                portfolio = json.load(f)

            # Update name and timestamp
            portfolio["name"] = new_name
            portfolio["last_modified"] = datetime.now().isoformat()

            # Save with new name
            with open(new_path, "w", encoding="utf-8") as f:
                json.dump(portfolio, f, indent=2, ensure_ascii=False)

            # Delete old file
            old_path.unlink()

            # Update recent visits to use new name
            cls._rename_recent_entry(old_name, new_name)
            return True
        except (json.JSONDecodeError, IOError, OSError) as e:
            print(f"Error renaming portfolio {old_name} to {new_name}: {e}")
            return False

    @classmethod
    def record_visit(cls, name: str) -> None:
        """
        Record a portfolio visit for recent ordering.

        Args:
            name: Portfolio name that was visited
        """
        recent = cls._load_recent()
        recent[name] = datetime.now().isoformat()
        cls._save_recent(recent)

    @classmethod
    def list_portfolios_by_recent(cls) -> List[str]:
        """
        List all portfolios sorted by most recently visited.

        Returns:
            List of portfolio names, most recently visited first
        """
        all_portfolios = cls.list_portfolios()
        if not all_portfolios:
            return []

        recent = cls._load_recent()

        # Sort: portfolios with recent visits first (by timestamp desc),
        # then unvisited portfolios alphabetically
        def sort_key(name: str):
            if name in recent:
                # Visited portfolios: sort by timestamp descending (negate for desc)
                # Use tuple: (0, negative_timestamp) to sort visited first
                try:
                    ts = datetime.fromisoformat(recent[name])
                    return (0, -ts.timestamp())
                except (ValueError, TypeError):
                    return (1, name.lower())
            else:
                # Unvisited portfolios: sort alphabetically after visited ones
                return (1, name.lower())

        return sorted(all_portfolios, key=sort_key)

    @classmethod
    def remove_from_recent(cls, name: str) -> None:
        """
        Remove a portfolio from recent visits (e.g., when deleted).

        Args:
            name: Portfolio name to remove
        """
        recent = cls._load_recent()
        if name in recent:
            del recent[name]
            cls._save_recent(recent)

    @classmethod
    def _rename_recent_entry(cls, old_name: str, new_name: str) -> None:
        """
        Update recent visits when a portfolio is renamed.

        Args:
            old_name: Old portfolio name
            new_name: New portfolio name
        """
        recent = cls._load_recent()
        if old_name in recent:
            recent[new_name] = recent.pop(old_name)
            cls._save_recent(recent)

    @classmethod
    def _load_recent(cls) -> Dict[str, str]:
        """Load recent visits from disk."""
        if not cls._RECENT_FILE.exists():
            return {}
        try:
            with open(cls._RECENT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    @classmethod
    def _save_recent(cls, recent: Dict[str, str]) -> None:
        """Save recent visits to disk."""
        try:
            cls._RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(cls._RECENT_FILE, "w", encoding="utf-8") as f:
                json.dump(recent, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving recent portfolios: {e}")
