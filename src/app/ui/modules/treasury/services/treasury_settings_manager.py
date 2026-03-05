"""Treasury Settings Manager - Persistent settings for the Treasury module."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt

from app.services.base_settings_manager import BaseSettingsManager
from app.services.qt_settings_mixin import QtSettingsSerializationMixin


class TreasurySettingsManager(QtSettingsSerializationMixin, BaseSettingsManager):
    """Settings manager for the Treasury module."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_gridlines": True,
            "show_crosshair": True,
            "show_value_label": True,
            "show_date_label": True,
            # Yield Curve view
            "show_fed_funds": True,
            # Rates view
            "rate_series": ["2Y", "5Y", "10Y", "30Y"],
            "show_fed_funds_rate": False,
            # Spread view
            "show_inversion_shading": True,
            "show_zero_line": True,
            # Line settings
            "line_color": None,  # None = theme accent
            "line_width": 2,
            "line_style": Qt.SolidLine,
        }

    @property
    def settings_filename(self) -> str:
        return "treasury_settings.json"

