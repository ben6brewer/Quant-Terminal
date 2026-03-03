from typing import Any, Dict
from app.services.base_settings_manager import BaseSettingsManager


class MoneySupplySettingsManager(BaseSettingsManager):
    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_m1": True,
            "show_m2": True,
            "view_mode": "Raw",
            "show_recession_bands": True,
            "show_gridlines": True,
            "show_crosshair": True,
            "show_legend": True,
            "show_hover_tooltip": True,
            "lookback": "10Y",
        }

    @property
    def settings_filename(self) -> str:
        return "money_supply_settings.json"
