"""Wealth Distribution Module — Wealth share by percentile (stacked area)."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.wealth_inequality.services import WealthInequalityFredService
from .widgets.wealth_distribution_chart import WealthDistributionChart


class WealthDistributionModule(FredDataModule):
    """Wealth Distribution module — stacked area of wealth shares by percentile."""

    SETTINGS_FILENAME = "wealth_distribution_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Stacked Area",
        "show_top1": True,
        "show_90_99": True,
        "show_50_90": True,
        "show_bottom50": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }
    VIEW_MODE = "view_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Stacked Area", "Line"],
            stat_labels=[("top1_label", "Top 1%: --"), ("bottom50_label", "Bottom 50%: --")],
            lookback_options=["5Y", "10Y", "20Y", "Max"],
            default_lookback_index=3,
        )

    def create_chart(self):
        return WealthDistributionChart()

    def get_fred_service(self):
        return WealthInequalityFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching wealth distribution data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch wealth distribution data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def update_toolbar_info(self, result):
        stats = WealthInequalityFredService.get_latest_stats(result)
        if stats:
            top1 = stats.get("top1")
            if top1 is not None:
                self.toolbar.top1_label.setText(f"Top 1%: {top1:.1f}%")
            bottom50 = stats.get("bottom50")
            if bottom50 is not None:
                self.toolbar.bottom50_label.setText(f"Bottom 50%: {bottom50:.1f}%")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        wealth_df = self.slice_data(result.get("wealth_shares"))
        usrec_df = result.get("usrec")
        return (wealth_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_top1", "Show Top 1%"),
            ("show_90_99", "Show 90th-99th"),
            ("show_50_90", "Show 50th-90th"),
            ("show_bottom50", "Show Bottom 50%"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Wealth Distribution Settings"
