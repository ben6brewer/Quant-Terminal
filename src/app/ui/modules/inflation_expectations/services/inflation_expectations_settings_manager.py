from typing import Any, Dict
from app.services.base_settings_manager import BaseSettingsManager

class InflationExpectationsSettingsManager(BaseSettingsManager):
    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_gridlines": True,
            "show_crosshair": True,
            "show_legend": True,
            "show_hover_tooltip": True,
            "show_reference_line": True,
            "lookback": "5Y",
        }

    @property
    def settings_filename(self) -> str:
        return "inflation_expectations_settings.json"
