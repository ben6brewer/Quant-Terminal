"""OLS Settings Manager - Persistent settings for OLS Regression module."""

from typing import Dict, Any

from app.services.base_settings_manager import BaseSettingsManager


class OLSSettingsManager(BaseSettingsManager):
    """Settings for the OLS Regression module."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "ticker_x": "",
            "ticker_y": "",
            "data_mode": "simple_returns",
            "frequency": "daily",
            "lookback_days": None,
            "show_gridlines": True,
            "show_confidence_bands": True,
            "show_equation": True,
            "show_stats_panel": True,
        }

    @property
    def settings_filename(self) -> str:
        return "ols_regression_settings.json"

    def get_ticker_x(self) -> str:
        return self.get_setting("ticker_x") or ""

    def get_ticker_y(self) -> str:
        return self.get_setting("ticker_y") or ""

    def get_data_mode(self) -> str:
        return self.get_setting("data_mode") or "simple_returns"

    def get_frequency(self) -> str:
        return self.get_setting("frequency") or "daily"

    def get_lookback_days(self):
        return self.get_setting("lookback_days")

    def get_show_gridlines(self) -> bool:
        val = self.get_setting("show_gridlines")
        return val if val is not None else True

    def get_show_confidence_bands(self) -> bool:
        val = self.get_setting("show_confidence_bands")
        return val if val is not None else True

    def get_show_equation(self) -> bool:
        val = self.get_setting("show_equation")
        return val if val is not None else True

    def get_show_stats_panel(self) -> bool:
        val = self.get_setting("show_stats_panel")
        return val if val is not None else True
