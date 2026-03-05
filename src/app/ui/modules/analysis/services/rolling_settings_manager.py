"""Rolling Settings Manager - Persistent settings for rolling correlation/covariance."""

from typing import Dict, Any

from PySide6.QtCore import Qt

from app.services.base_settings_manager import BaseSettingsManager
from app.services.qt_settings_mixin import QtSettingsSerializationMixin


class RollingSettingsManager(QtSettingsSerializationMixin, BaseSettingsManager):
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
