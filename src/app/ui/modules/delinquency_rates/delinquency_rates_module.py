"""Delinquency Rates Module — Multi-line delinquency rates from FRED."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.credit.services import CreditFredService
from .widgets.delinquency_rates_toolbar import DelinquencyRatesToolbar
from .widgets.delinquency_rates_chart import DelinquencyRatesChart


class DelinquencyRatesModule(FredDataModule):
    """Delinquency Rates module — CC / All Loans / Consumer Loans delinquency %."""

    SETTINGS_FILENAME = "delinquency_rates_settings.json"
    DEFAULT_SETTINGS = {
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return DelinquencyRatesToolbar(self.theme_manager)

    def create_chart(self):
        return DelinquencyRatesChart()

    def get_fred_service(self):
        return CreditFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching delinquency data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch delinquency data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def get_lookback_options(self):
        return ["5Y", "10Y", "20Y", "Max"]

    def update_toolbar_info(self, result):
        stats = CreditFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(cc_delinquency=stats.get("cc_delinquency"))

    def extract_chart_data(self, result):
        delinq_df = self.slice_data(result.get("delinquency"))
        usrec_df = result.get("usrec")
        return (delinq_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Delinquency Rates Settings"
