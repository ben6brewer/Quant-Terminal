from typing import Any, Dict

from app.services.base_settings_manager import BaseSettingsManager


class LaborMarketOverviewSettingsManager(BaseSettingsManager):
    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_gridlines": True,
            "show_crosshair": True,
            "show_legend": True,
            "show_hover_tooltip": True,
            "show_recession_shading": True,
            "show_u6": False,
            "lookback": "5Y",
        }

    @property
    def settings_filename(self) -> str:
        return "labor_market_overview_settings.json"
