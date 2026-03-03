from typing import Any, Dict
from app.services.base_settings_manager import BaseSettingsManager


class MoneyVelocitySettingsManager(BaseSettingsManager):
    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_recession_bands": True,
            "show_gridlines": True,
            "show_crosshair": True,
            "show_hover_tooltip": True,
            "lookback": "Max",
        }

    @property
    def settings_filename(self) -> str:
        return "money_velocity_settings.json"
