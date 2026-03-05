"""Mortgage Rates Module — Multi-line: 30Y and 15Y fixed rates."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_WEEKS
from app.ui.modules.mortgage.services import MortgageFredService
from .widgets.mortgage_rates_toolbar import MortgageRatesToolbar
from .widgets.mortgage_rates_chart import MortgageRatesChart


class MortgageRatesModule(FredDataModule):
    """Mortgage Rates module — 30Y + 15Y fixed rates from FRED."""

    SETTINGS_FILENAME = "mortgage_rates_settings.json"
    DEFAULT_SETTINGS = {
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return MortgageRatesToolbar(self.theme_manager)

    def create_chart(self):
        return MortgageRatesChart()

    def get_fred_service(self):
        return MortgageFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching mortgage rate data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch mortgage rate data."

    def get_lookback_map(self):
        return LOOKBACK_WEEKS

    def update_toolbar_info(self, result):
        stats = MortgageFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                rate_30y=stats.get("rate_30y"),
                rate_15y=stats.get("rate_15y"),
            )

    def extract_chart_data(self, result):
        rates_df = self.slice_data(result.get("rates"))
        usrec_df = result.get("usrec")
        return (rates_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Mortgage Rates Settings"
