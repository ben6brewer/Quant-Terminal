from typing import Any, Dict
from app.services.base_settings_manager import BaseSettingsManager

class PpiSettingsManager(BaseSettingsManager):
    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_gridlines": True,
            "show_crosshair": True,
            "show_legend": True,
            "show_hover_tooltip": True,
            "lookback": "5Y",
            "show_ppi_final_demand": True,
            "show_ppi_core": True,
            "show_ppi_energy": True,
            "show_ppi_services": True,
        }

    @property
    def settings_filename(self) -> str:
        return "ppi_settings.json"
