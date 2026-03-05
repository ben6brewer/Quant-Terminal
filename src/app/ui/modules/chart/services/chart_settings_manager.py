"""Chart Settings Manager - Manages chart appearance settings with persistence."""

from __future__ import annotations

from typing import Dict, Any, Tuple
from PySide6.QtCore import Qt

from app.services.base_settings_manager import BaseSettingsManager
from app.services.qt_settings_mixin import QtSettingsSerializationMixin


class ChartSettingsManager(QtSettingsSerializationMixin, BaseSettingsManager):
    """Manages chart appearance settings with persistent storage."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        """Default chart settings."""
        return {
            # Candle colors (RGB tuples)
            "candle_up_color": (76, 153, 0),
            "candle_down_color": (200, 50, 50),

            # Chart background (None means use theme default)
            "chart_background": None,

            # Candle width
            "candle_width": 0.6,

            # Line chart settings
            "line_color": None,  # None means use theme default
            "line_width": 2,
            "line_style": Qt.SolidLine,

            # Price label
            "show_price_label": True,

            # Date label (crosshair)
            "show_date_label": True,
        }

    @property
    def settings_filename(self) -> str:
        """Settings file name."""
        return "chart_settings.json"

    def get_candle_colors(self) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """Get candle up and down colors."""
        up = self._settings.get("candle_up_color", self.DEFAULT_SETTINGS["candle_up_color"])
        down = self._settings.get("candle_down_color", self.DEFAULT_SETTINGS["candle_down_color"])
        return up, down

    def get_line_settings(self) -> Dict[str, Any]:
        """Get line chart settings."""
        return {
            "color": self._settings.get("line_color"),
            "width": self._settings.get("line_width", 2),
            "style": self._settings.get("line_style", Qt.SolidLine),
        }
