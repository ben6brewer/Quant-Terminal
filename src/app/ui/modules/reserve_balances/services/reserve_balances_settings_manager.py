from typing import Any, Dict
from app.services.base_settings_manager import BaseSettingsManager


class ReserveBalancesSettingsManager(BaseSettingsManager):
    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_total_assets_overlay": False,
            "show_recession_bands": True,
            "show_gridlines": True,
            "show_crosshair": True,
            "show_legend": True,
            "show_hover_tooltip": True,
            "lookback": "Max",
        }

    @property
    def settings_filename(self) -> str:
        return "reserve_balances_settings.json"
