"""Rate Probability Settings Manager - Persistent settings for the module."""

from __future__ import annotations

from typing import Any, Dict

from app.services.base_settings_manager import BaseSettingsManager


class RateProbabilitySettingsManager(BaseSettingsManager):
    """Settings manager for the Rate Probability module."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_gridlines": True,
            "show_probability_table": True,
            "show_futures_table": True,
        }

    @property
    def settings_filename(self) -> str:
        return "rate_probability_settings.json"
