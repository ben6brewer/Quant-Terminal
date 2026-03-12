"""Mortgage Rates Module — Multi-line: 30Y and 15Y fixed rates."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_WEEKS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.mortgage.services import MortgageFredService
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
        return FredToolbar(
            self.theme_manager,
            stat_labels=[("rate30_label", "30Y: --"), ("rate15_label", "15Y: --")],
        )

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
            rate_30y = stats.get("rate_30y")
            rate_15y = stats.get("rate_15y")
            if rate_30y is not None:
                self.toolbar.rate30_label.setText(f"30Y: {rate_30y:.2f}%")
            if rate_15y is not None:
                self.toolbar.rate15_label.setText(f"15Y: {rate_15y:.2f}%")
        self.toolbar._update_timestamp()

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
