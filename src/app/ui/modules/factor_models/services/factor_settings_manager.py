"""Factor Models Settings Manager — persistent settings."""

from typing import Dict, Any

from app.services.base_settings_manager import BaseSettingsManager


class FactorSettingsManager(BaseSettingsManager):
    """Settings for the Factor Models module."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "input_mode": "ticker",
            "ticker": "",
            "portfolio": "",
            "model_key": "ff5mom",
            "frequency": "monthly",
            "lookback_days": 1825,
            "custom_start_date": None,
            "custom_end_date": None,
            "view_mode": "cumulative",
            "show_gridlines": True,
            "show_stats_panel": True,
        }

    @property
    def settings_filename(self) -> str:
        return "factor_models_settings.json"
