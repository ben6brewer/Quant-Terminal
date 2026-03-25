"""Custom Model Store — factor catalog & CRUD persistence for user-created factor models."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .model_definitions import FactorModelSpec

logger = logging.getLogger(__name__)

# ── Factor Catalog ───────────────────────────────────────────────────────────
# Every selectable factor grouped by data source.
# Mkt-RF is always auto-included and not shown in the catalog.

FACTOR_CATALOG: dict[str, list[tuple[str, str]]] = {
    "Fama-French": [
        ("SMB", "Size"),
        ("HML", "Value"),
        ("RMW", "Profitability"),
        ("CMA", "Investment"),
        ("UMD", "Momentum"),
    ],
    "Q-Factor (HXZ)": [
        ("R_ME", "Size"),
        ("R_IA", "Investment"),
        ("R_ROE", "Profitability"),
        ("R_EG", "Expected Growth"),
    ],
    "AQR": [
        ("BAB", "Betting Against Beta"),
        ("QMJ", "Quality Minus Junk"),
        ("HML_DEVIL", "HML Devil"),
    ],
}

# Which column names belong to which data source (for source detection)
_FF_FACTORS = {"Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"}
_Q_FACTORS = {"R_MKT", "R_ME", "R_IA", "R_ROE", "R_EG"}
_AQR_FACTORS = {"BAB", "QMJ", "HML_DEVIL"}

_SETTINGS_DIR = Path.home() / ".quant_terminal"
_STORE_FILE = _SETTINGS_DIR / "custom_factor_models.json"


class CustomModelStore:
    """Load / save / CRUD for user-created custom factor models."""

    # ── Read ─────────────────────────────────────────────────────────────

    @classmethod
    def list_models(cls) -> list[FactorModelSpec]:
        """Return all saved custom models as FactorModelSpec instances."""
        entries = cls._read_file()
        return [cls._entry_to_spec(e) for e in entries]

    @classmethod
    def get_model(cls, key: str) -> Optional[FactorModelSpec]:
        """Return a single custom model by key, or None."""
        for e in cls._read_file():
            if e["key"] == key:
                return cls._entry_to_spec(e)
        return None

    # ── Write ────────────────────────────────────────────────────────────

    @classmethod
    def save_model(cls, name: str, factors: list[str]) -> FactorModelSpec:
        """Create a new custom model and persist it. Returns the spec."""
        entries = cls._read_file()
        key = cls._make_key(name, entries)
        factors = cls._ensure_market(factors)
        entry = {"name": name, "key": key, "factors": factors}
        entries.append(entry)
        cls._write_file(entries)
        return cls._entry_to_spec(entry)

    @classmethod
    def update_model(cls, key: str, name: str, factors: list[str]) -> FactorModelSpec:
        """Update an existing custom model in place."""
        entries = cls._read_file()
        factors = cls._ensure_market(factors)
        for e in entries:
            if e["key"] == key:
                e["name"] = name
                e["factors"] = factors
                cls._write_file(entries)
                return cls._entry_to_spec(e)
        raise KeyError(f"Custom model '{key}' not found")

    @classmethod
    def delete_model(cls, key: str) -> bool:
        """Delete a custom model. Returns True if found and deleted."""
        entries = cls._read_file()
        before = len(entries)
        entries = [e for e in entries if e["key"] != key]
        if len(entries) < before:
            cls._write_file(entries)
            return True
        return False

    # ── Helpers ──────────────────────────────────────────────────────────

    @classmethod
    def existing_names(cls, exclude_key: str = "") -> set[str]:
        """Return set of existing custom model names (for uniqueness checks)."""
        return {
            e["name"] for e in cls._read_file() if e["key"] != exclude_key
        }

    @staticmethod
    def _ensure_market(factors: list[str]) -> list[str]:
        """Ensure Mkt-RF is first in the factors list."""
        factors = [f for f in factors if f != "Mkt-RF"]
        return ["Mkt-RF"] + factors

    @staticmethod
    def _make_key(name: str, entries: list[dict]) -> str:
        """Generate a unique key from the model name."""
        base = "custom_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        existing = {e["key"] for e in entries}
        key = base
        n = 2
        while key in existing:
            key = f"{base}_{n}"
            n += 1
        return key

    @staticmethod
    def _entry_to_spec(entry: dict) -> FactorModelSpec:
        """Convert a JSON entry to a FactorModelSpec."""
        factors = tuple(entry["factors"])
        has_aqr = bool(set(factors) & _AQR_FACTORS)
        return FactorModelSpec(
            name=entry["name"],
            key=entry["key"],
            factors=factors,
            source="custom",
            description=f"Custom model: {', '.join(factors[1:])}",
            min_frequency="monthly" if has_aqr else "daily",
        )

    # ── File I/O ─────────────────────────────────────────────────────────

    @classmethod
    def _read_file(cls) -> list[dict]:
        if not _STORE_FILE.exists():
            return []
        try:
            with open(_STORE_FILE, "r") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning("Failed to read custom models: %s", e)
            return []

    @classmethod
    def _write_file(cls, entries: list[dict]) -> None:
        try:
            _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            with open(_STORE_FILE, "w") as f:
                json.dump(entries, f, indent=2)
        except Exception as e:
            logger.warning("Failed to write custom models: %s", e)
