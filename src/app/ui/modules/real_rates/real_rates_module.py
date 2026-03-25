"""Real Rates Module — Real interest rates and TIPS yields."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_DAYS
from app.ui.modules.fred_toolbar import FredToolbar
from .services import RealRatesFredService
from .widgets.real_rates_chart import RealRatesChart


class RealRatesModule(FredDataModule):
    """Real Rates module — TIPS yields and real rate tracking."""

    SETTINGS_FILENAME = "real_rates_settings.json"
    DEFAULT_SETTINGS = {
        "show_tips_5y": True,
        "show_tips_10y": True,
        "show_tips_20y": True,
        "show_tips_30y": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            stat_labels=[('tips10_label', '10Y TIPS: --')],
            lookback_options=['1Y', '2Y', '5Y', '10Y', '20Y', 'Max'],
            default_lookback_index=2,
        )

    def create_chart(self):
        return RealRatesChart()

    def get_fred_service(self):
        return RealRatesFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching real rates data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch real rates data."

    def get_lookback_map(self):
        return LOOKBACK_DAYS

    def update_toolbar_info(self, result):
        stats = RealRatesFredService.get_latest_stats(result)
        if stats:
            tips10 = stats.get("tips10")
            if tips10 is not None:
                self.toolbar.tips10_label.setText(f"10Y TIPS: {tips10:.2f}%")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        tips_df = self.slice_data(result.get("tips"))
        usrec_df = result.get("usrec")
        return (tips_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_tips_5y", "Show 5Y TIPS"),
            ("show_tips_10y", "Show 10Y TIPS"),
            ("show_tips_20y", "Show 20Y TIPS"),
            ("show_tips_30y", "Show 30Y TIPS"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Real Rates Settings"
