"""Wage Growth Module — Dual-view: Raw levels or YoY% growth."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.income.services import IncomeFredService
from .widgets.wage_growth_toolbar import WageGrowthToolbar
from .widgets.wage_growth_chart import WageGrowthChart


class WageGrowthModule(FredDataModule):
    """Wage Growth module — dual-mode: Raw (AHE $/hr + ECI index) or YoY%."""

    SETTINGS_FILENAME = "wage_growth_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "YoY %",
        "show_ahe": True,
        "show_eci": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return WageGrowthToolbar(self.theme_manager)

    def create_chart(self):
        return WageGrowthChart()

    def get_fred_service(self):
        return IncomeFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching wage growth data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch wage growth data."

    def update_toolbar_info(self, result):
        stats = IncomeFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                ahe_yoy=stats.get("ahe_yoy"),
                eci_yoy=stats.get("eci_yoy"),
                ahe_raw=stats.get("ahe_raw"),
            )

    def extract_chart_data(self, result):
        wages_raw_df = self.slice_data(result.get("wages_raw"))
        wages_df = self.slice_data(result.get("wages"))
        usrec_df = result.get("usrec")
        return (wages_raw_df, wages_df, usrec_df)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({"view_mode": view})
        self._render()

    def _apply_extra_settings(self):
        self.toolbar.set_active_view(self.settings_manager.get_setting("view_mode"))

    def get_settings_options(self):
        return [
            ("show_ahe", "Show Avg Hourly Earnings"),
            ("show_eci", "Show ECI Wages"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Wage Growth Settings"
