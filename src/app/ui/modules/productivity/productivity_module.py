"""Productivity Module — Multi-line YoY%: Productivity, ULC, Real Compensation."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.productivity_service.services import ProductivityFredService
from .widgets.productivity_toolbar import ProductivityToolbar
from .widgets.productivity_chart import ProductivityChart


class ProductivityModule(FredDataModule):
    """Productivity module — YoY% multi-line from FRED (quarterly)."""

    SETTINGS_FILENAME = "productivity_settings.json"
    DEFAULT_SETTINGS = {
        "show_productivity": True,
        "show_ulc": True,
        "show_real_comp": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return ProductivityToolbar(self.theme_manager)

    def create_chart(self):
        return ProductivityChart()

    def get_fred_service(self):
        return ProductivityFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching productivity data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch productivity data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def update_toolbar_info(self, result):
        stats = ProductivityFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                productivity=stats.get("productivity"),
                ulc=stats.get("ulc"),
            )

    def extract_chart_data(self, result):
        prod_df = self.slice_data(result.get("productivity"))
        usrec_df = result.get("usrec")
        return (prod_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_productivity", "Show Productivity"),
            ("show_ulc", "Show Unit Labor Costs"),
            ("show_real_comp", "Show Real Compensation"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Productivity Settings"
