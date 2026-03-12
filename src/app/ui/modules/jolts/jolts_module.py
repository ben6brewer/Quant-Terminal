"""JOLTS Module - Openings, Hires, Quits, Layoffs lines."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.labor_market.services import LaborMarketFredService
from .widgets.jolts_toolbar import JoltsToolbar
from .widgets.jolts_chart import JoltsChart


class JoltsModule(FredDataModule):
    """JOLTS module — job openings, hires, quits, layoffs from FRED."""

    SETTINGS_FILENAME = "jolts_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "show_recession_shading": True,
        "jolts_series": ["Job Openings", "Hires", "Quits", "Layoffs"],
        "lookback": "5Y",
    }
    VIEW_MODE = "view_mode"

    def create_toolbar(self):
        return JoltsToolbar(self.theme_manager)

    def create_chart(self):
        return JoltsChart()

    def get_fred_service(self):
        return LaborMarketFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching JOLTS data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch JOLTS data."

    def update_toolbar_info(self, result):
        stats = LaborMarketFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(openings=stats.get("openings"))

    def extract_chart_data(self, result):
        jolts = self.slice_data(result.get("jolts"))
        usrec = result.get("usrec")
        return (jolts, usrec)

    def create_settings_dialog(self, current_settings):
        from .widgets.jolts_settings_dialog import JoltsSettingsDialog
        return JoltsSettingsDialog(
            self.theme_manager,
            current_settings=current_settings,
            parent=self,
        )
