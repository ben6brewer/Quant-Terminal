"""Labor Market Overview Module - Full UNRATE history with optional U-6 overlay."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.labor_market.services import LaborMarketFredService
from .widgets.labor_market_overview_toolbar import LaborMarketOverviewToolbar
from .widgets.labor_market_overview_chart import LaborMarketOverviewChart


class LaborMarketOverviewModule(FredDataModule):
    """Unemployment Rate module — full U-3 history with optional U-6 and recession shading."""

    SETTINGS_FILENAME = "labor_market_overview_settings.json"
    DEFAULT_SETTINGS = {
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "show_recession_shading": True,
        "show_u6": False,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return LaborMarketOverviewToolbar(self.theme_manager)

    def create_chart(self):
        return LaborMarketOverviewChart()

    def get_fred_service(self):
        return LaborMarketFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching unemployment data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch unemployment data."

    def update_toolbar_info(self, result):
        stats = LaborMarketFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(unrate=stats.get("unrate"))

    def extract_chart_data(self, result):
        rates = self.slice_data(result.get("rates"))
        usrec = result.get("usrec")
        return (rates, usrec)

    def get_settings_options(self):
        return [
            ("show_gridlines", "Show Gridlines"),
            ("show_crosshair", "Show Crosshair"),
            ("show_legend", "Show Legend"),
            ("show_hover_tooltip", "Show Hover Tooltip"),
            ("show_recession_shading", "Show NBER Recession Shading"),
            ("show_u6", "Show U-6 rate"),
        ]

    def get_settings_dialog_title(self):
        return "Labor Market Settings"
