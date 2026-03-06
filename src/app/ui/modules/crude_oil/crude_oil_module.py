"""Crude Oil Module — Multi-line: WTI + Brent."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_DAYS
from app.ui.modules.commodities.services import CommodityFredService
from .widgets.crude_oil_toolbar import CrudeOilToolbar
from .widgets.crude_oil_chart import CrudeOilChart


class CrudeOilModule(FredDataModule):
    """Crude Oil module — WTI + Brent from FRED."""

    SETTINGS_FILENAME = "crude_oil_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_wti": True,
        "show_brent": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return CrudeOilToolbar(self.theme_manager)

    def create_chart(self):
        return CrudeOilChart()

    def get_fred_service(self):
        return CommodityFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching crude oil data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch crude oil data."

    def get_lookback_map(self):
        return LOOKBACK_DAYS

    def update_toolbar_info(self, result):
        stats = CommodityFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                wti=stats.get("wti"),
                brent=stats.get("brent"),
            )

    def extract_chart_data(self, result):
        energy_df = self.slice_data(result.get("energy"))
        if energy_df is not None:
            cols = [c for c in ["WTI Crude", "Brent Crude"] if c in energy_df.columns]
            energy_df = energy_df[cols] if cols else energy_df
        usrec_df = result.get("usrec")
        return (energy_df, usrec_df)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({"view_mode": view})
        self._render()

    def _apply_extra_settings(self):
        self.toolbar.set_active_view(self.settings_manager.get_setting("view_mode"))

    def get_settings_options(self):
        return [
            ("show_wti", "Show WTI Crude"),
            ("show_brent", "Show Brent Crude"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Crude Oil Settings"
