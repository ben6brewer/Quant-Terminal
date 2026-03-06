"""Labor Claims Module - Initial + Continued claims + 4-week MA."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_MONTHS
from app.ui.modules.labor_market.services import LaborMarketFredService
from .widgets.labor_claims_toolbar import LaborClaimsToolbar
from .widgets.labor_claims_chart import LaborClaimsChart

if TYPE_CHECKING:
    import pandas as pd


class LaborClaimsModule(FredDataModule):
    """Labor claims module — initial + continued claims + 4-week MA from FRED."""

    SETTINGS_FILENAME = "labor_claims_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "show_recession_shading": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return LaborClaimsToolbar(self.theme_manager)

    def create_chart(self):
        return LaborClaimsChart()

    def get_fred_service(self):
        return LaborMarketFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching claims data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch claims data."

    def update_toolbar_info(self, result):
        stats = LaborMarketFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(claims=stats.get("claims"))

    def slice_data(self, df: "Optional[pd.DataFrame]") -> "Optional[pd.DataFrame]":
        """Slice weekly DataFrame (approximate weeks from months)."""
        if df is None or df.empty:
            return df
        lb = self._current_lookback
        if isinstance(lb, str) and "-" in lb:
            return df.loc[lb:]
        months = LOOKBACK_MONTHS.get(lb)
        if months is None:
            return df
        weeks = int(months * 4.33)
        return df.tail(weeks)

    def extract_chart_data(self, result):
        claims = self.slice_data(result.get("claims"))
        usrec = result.get("usrec")
        return (claims, usrec)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({"view_mode": view})
        self._render()

    def _apply_extra_settings(self):
        self.toolbar.set_active_view(self.settings_manager.get_setting("view_mode"))

    def get_settings_options(self):
        return [
            ("show_gridlines", "Show Gridlines"),
            ("show_crosshair", "Show Crosshair"),
            ("show_legend", "Show Legend"),
            ("show_hover_tooltip", "Show Hover Tooltip"),
            ("show_recession_shading", "Show NBER Recession Shading"),
        ]

    def get_settings_dialog_title(self):
        return "Labor Claims Settings"
