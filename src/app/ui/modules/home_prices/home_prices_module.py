"""Home Prices Module — Median and average sale prices from FRED."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.home_market.services import HomeMarketFredService
from .widgets.home_prices_chart import HomePricesChart


class HomePricesModule(FredDataModule):
    """Home Prices module — median and average sale prices."""

    SETTINGS_FILENAME = "home_prices_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_median_price": True,
        "show_avg_price": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }
    VIEW_MODE = "view_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "YoY %"],
            stat_labels=[("median_label", "Median: --"), ("avg_label", "Avg: --")],
            default_lookback_index=3,
        )

    def create_chart(self):
        return HomePricesChart()

    def get_fred_service(self):
        return HomeMarketFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching home price data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch home price data."

    def update_toolbar_info(self, result):
        stats = HomeMarketFredService.get_latest_stats(result)
        if stats:
            median = stats.get("median")
            if median is not None:
                self.toolbar.median_label.setText(f"Median: ${median:,.0f}K")
            avg = stats.get("avg")
            if avg is not None:
                self.toolbar.avg_label.setText(f"Avg: ${avg:,.0f}K")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        sale_prices_df = self.slice_data(result.get("sale_prices"))
        usrec_df = result.get("usrec")
        return (sale_prices_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_median_price", "Show Median Sale Price"),
            ("show_avg_price", "Show Average Sale Price"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Home Prices Settings"
