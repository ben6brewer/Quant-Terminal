"""CPI Settings Manager - Persistent settings for the CPI module."""

from __future__ import annotations

from typing import Any, Dict

from app.services.base_settings_manager import BaseSettingsManager


class CpiSettingsManager(BaseSettingsManager):
    """Settings manager for the CPI module."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_breakdown": True,
            "show_gridlines": True,
            "show_reference_lines": True,  # Fed 2% target
            "show_crosshair": True,
            "show_value_label": True,
            "show_date_label": True,
            "show_hover_tooltip": True,      # Breakdown: hover component tooltip
            "show_headline_overlay": True,   # Breakdown: headline CPI line overlay
            "show_legend": True,             # Breakdown: component color legend
        }

    @property
    def settings_filename(self) -> str:
        return "cpi_settings.json"
