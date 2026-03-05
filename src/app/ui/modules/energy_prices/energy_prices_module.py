"""Energy Prices Module — Multi-line: WTI, Brent, Natural Gas."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_WEEKS
from app.ui.modules.commodities.services import CommodityFredService
from .widgets.energy_prices_toolbar import EnergyPricesToolbar
from .widgets.energy_prices_chart import EnergyPricesChart


class EnergyPricesModule(FredDataModule):
    """Energy Prices module — WTI, Brent, Natural Gas from FRED."""

    SETTINGS_FILENAME = "energy_prices_settings.json"
    DEFAULT_SETTINGS = {
        "show_wti": True,
        "show_brent": True,
        "show_natgas": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return EnergyPricesToolbar(self.theme_manager)

    def create_chart(self):
        return EnergyPricesChart()

    def get_fred_service(self):
        return CommodityFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching energy price data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch energy price data."

    def get_lookback_map(self):
        return LOOKBACK_WEEKS

    def update_toolbar_info(self, result):
        stats = CommodityFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                wti=stats.get("wti"),
                brent=stats.get("brent"),
                natgas=stats.get("natgas"),
            )

    def extract_chart_data(self, result):
        energy_df = self.slice_data(result.get("energy"))
        usrec_df = result.get("usrec")
        return (energy_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_wti", "Show WTI Crude"),
            ("show_brent", "Show Brent Crude"),
            ("show_natgas", "Show Natural Gas"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Energy Prices Settings"
