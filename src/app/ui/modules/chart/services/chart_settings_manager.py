"""Chart Settings Manager - Manages chart appearance settings with persistence."""

from __future__ import annotations

from typing import Dict, Any, Tuple
from PySide6.QtCore import Qt

from app.services.base_settings_manager import BaseSettingsManager


class ChartSettingsManager(BaseSettingsManager):
    """
    Manages chart appearance settings with persistent storage.

    Extends BaseSettingsManager with chart-specific:
    - Qt.PenStyle serialization for line styles
    - RGB tuple serialization for colors
    - Helper methods for candle and line settings
    """

    # Qt PenStyle mapping for JSON serialization
    _PENSTYLE_TO_STR = {
        Qt.SolidLine: "solid",
        Qt.DashLine: "dash",
        Qt.DotLine: "dot",
        Qt.DashDotLine: "dashdot",
    }

    _STR_TO_PENSTYLE = {
        "solid": Qt.SolidLine,
        "dash": Qt.DashLine,
        "dot": Qt.DotLine,
        "dashdot": Qt.DashDotLine,
    }

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

    def _serialize_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Convert settings to JSON-serializable format."""
        serialized = {}

        for key, value in settings.items():
            if isinstance(value, Qt.PenStyle):
                # Convert Qt.PenStyle to string
                serialized[key] = self._PENSTYLE_TO_STR.get(value, "solid")
            elif isinstance(value, tuple):
                # Convert tuples to lists for JSON
                serialized[key] = list(value)
            else:
                serialized[key] = value

        return serialized

    def _deserialize_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert settings from JSON format to runtime format."""
        deserialized = {}

        for key, value in data.items():
            if key == "line_style" and isinstance(value, str):
                # Convert string to Qt.PenStyle
                deserialized[key] = self._STR_TO_PENSTYLE.get(value, Qt.SolidLine)
            elif key in ["candle_up_color", "candle_down_color", "line_color"] and isinstance(value, list):
                # Convert lists to tuples for colors
                deserialized[key] = tuple(value) if value else None
            else:
                deserialized[key] = value

        return deserialized

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
