"""Savings Rate Module — Personal Savings Rate (%) from FRED."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.income.services import IncomeFredService
from .widgets.savings_rate_chart import SavingsRateChart


class SavingsRateModule(FredDataModule):
    """Savings Rate module — PSAVERT line with recession shading."""

    SETTINGS_FILENAME = "savings_rate_settings.json"
    DEFAULT_SETTINGS = {
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return FredToolbar(self.theme_manager,
                           stat_labels=[("rate_label", "Savings Rate: --")])

    def create_chart(self):
        return SavingsRateChart()

    def get_fred_service(self):
        return IncomeFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching savings rate data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch savings rate data."

    def update_toolbar_info(self, result):
        stats = IncomeFredService.get_latest_stats(result)
        if stats:
            savings_rate = stats.get("savings_rate")
            if savings_rate is not None:
                self.toolbar.rate_label.setText(f"Savings Rate: {savings_rate:.1f}%")
        self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        savings_df = self.slice_data(result.get("savings"))
        usrec_df = result.get("usrec")
        return (savings_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Savings Rate Settings"
