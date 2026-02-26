"""CPI Settings Manager - Persistent settings for the CPI module."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt

from app.services.base_settings_manager import BaseSettingsManager


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


class CpiSettingsManager(BaseSettingsManager):
    """Settings manager for the CPI module."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_gridlines": True,
            "show_reference_lines": True,  # Fed 2% target
            "show_crosshair": True,
            "show_value_label": True,
            "show_date_label": True,
            "show_hover_tooltip": True,      # Breakdown: hover component tooltip
            "show_headline_overlay": True,   # Breakdown: headline CPI line overlay
            "show_legend": True,             # Breakdown: component color legend
            "line_color": None,            # None = theme accent
            "line_width": 2,
            "line_style": Qt.SolidLine,
        }

    @property
    def settings_filename(self) -> str:
        return "cpi_settings.json"

    def _serialize_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        serialized = {}
        for key, value in settings.items():
            if isinstance(value, Qt.PenStyle):
                serialized[key] = _PENSTYLE_TO_STR.get(value, "solid")
            elif isinstance(value, tuple):
                serialized[key] = list(value)
            else:
                serialized[key] = value
        return serialized

    def _deserialize_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        deserialized = {}
        for key, value in data.items():
            if key == "line_style" and isinstance(value, str):
                deserialized[key] = _STR_TO_PENSTYLE.get(value, Qt.SolidLine)
            elif key == "line_color" and isinstance(value, list):
                deserialized[key] = tuple(value) if value else None
            else:
                deserialized[key] = value
        return deserialized
