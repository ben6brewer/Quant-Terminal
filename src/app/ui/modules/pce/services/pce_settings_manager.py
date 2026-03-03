from typing import Any, Dict
from app.services.base_settings_manager import BaseSettingsManager

class PceSettingsManager(BaseSettingsManager):
    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_gridlines": True,
            "show_crosshair": True,
            "show_legend": True,
            "show_hover_tooltip": True,
            "show_reference_line": True,
            "show_recession_shading": False,
            "lookback": "5Y",
            "show_pce": True,
            "show_core_pce": True,
        }

    @property
    def settings_filename(self) -> str:
        return "pce_settings.json"
