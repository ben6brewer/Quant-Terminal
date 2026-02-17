"""Rolling Settings Manager - Persistent settings for rolling correlation/covariance."""

from typing import Dict, Any

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


class RollingSettingsManager(BaseSettingsManager):
    """Settings for Rolling Correlation and Rolling Covariance modules."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "ticker1": "",
            "ticker2": "",
            "rolling_window": 63,
            "lookback_days": None,
            "show_gridlines": True,
            "show_reference_lines": True,
            "show_crosshair": True,
            "show_value_label": True,
            "show_date_label": True,
            "line_width": 2,
            "line_color": None,       # None = use theme accent
            "line_style": Qt.SolidLine,
        }

    @property
    def settings_filename(self) -> str:
        return "rolling_settings.json"

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

    def get_ticker1(self) -> str:
        return self.get_setting("ticker1") or ""

    def get_ticker2(self) -> str:
        return self.get_setting("ticker2") or ""

    def get_rolling_window(self) -> int:
        return self.get_setting("rolling_window") or 63

    def get_lookback_days(self):
        return self.get_setting("lookback_days")

    def get_show_gridlines(self) -> bool:
        val = self.get_setting("show_gridlines")
        return val if val is not None else True

    def get_show_reference_lines(self) -> bool:
        val = self.get_setting("show_reference_lines")
        return val if val is not None else True

    def get_line_width(self) -> int:
        return self.get_setting("line_width") or 2
