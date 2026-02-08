"""FRED API Key Service - Shared FRED API key management for all modules."""

import os
from pathlib import Path
from typing import Optional


class FredApiKeyService:
    """Shared FRED API key management - load/save/check from .env file."""

    _api_key: Optional[str] = None

    @classmethod
    def has_api_key(cls) -> bool:
        """Check if a FRED API key is available."""
        return cls._load_api_key() is not None

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Get the FRED API key."""
        return cls._load_api_key()

    @classmethod
    def set_api_key(cls, key: str) -> None:
        """Save FRED API key to .env file and update class cache."""
        env_path = Path(__file__).parent.parent.parent.parent / ".env"

        lines = []
        found = False
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if line.startswith("FRED_API_KEY="):
                        lines.append(f"FRED_API_KEY={key}\n")
                        found = True
                    else:
                        lines.append(line)

        if not found:
            lines.append(f"FRED_API_KEY={key}\n")

        with open(env_path, "w") as f:
            f.writelines(lines)

        cls._api_key = key

    @classmethod
    def _load_api_key(cls) -> Optional[str]:
        """Load FRED_API_KEY from .env file (cached)."""
        if cls._api_key is not None:
            return cls._api_key

        from dotenv import load_dotenv

        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        load_dotenv(env_path)

        cls._api_key = os.getenv("FRED_API_KEY") or None
        return cls._api_key
