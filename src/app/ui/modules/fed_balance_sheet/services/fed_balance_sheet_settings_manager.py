from typing import Any, Dict
from app.services.base_settings_manager import BaseSettingsManager


class FedBalanceSheetSettingsManager(BaseSettingsManager):
    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "show_breakdown": False,
            "show_treasuries": True,
            "show_mbs": True,
            "show_agency_debt": True,
            "show_loans": True,
            "show_other": True,
            "show_recession_bands": True,
            "show_gridlines": True,
            "show_crosshair": True,
            "show_legend": True,
            "show_hover_tooltip": True,
            "lookback": "10Y",
        }

    @property
    def settings_filename(self) -> str:
        return "fed_balance_sheet_settings.json"
