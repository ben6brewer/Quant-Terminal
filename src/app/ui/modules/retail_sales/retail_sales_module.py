"""Retail Sales Module — Dual-view: Raw two-line or YoY% growth."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.retail.services import RetailFredService
from .widgets.retail_sales_chart import RetailSalesChart


class RetailSalesModule(FredDataModule):
    """Retail Sales module — dual-mode: Raw (Total + Real) or YoY% line."""

    SETTINGS_FILENAME = "retail_sales_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "data_mode": "Nominal",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }
    VIEW_MODE = "view_mode"
    DATA_MODE = "data_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "YoY %"],
            data_mode_options=["Nominal", "Real"],
            stat_labels=[
                ("total_label", "Total: --"),
                ("mom_label", "MoM: --"),
            ],
        )

    def create_chart(self):
        return RetailSalesChart()

    def get_fred_service(self):
        return RetailFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching retail sales data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch retail sales data."

    def update_toolbar_info(self, result):
        stats = RetailFredService.get_latest_stats(result)
        if stats:
            retail_total = stats.get("retail_total")
            retail_mom = stats.get("retail_mom")
            if retail_total is not None:
                self.toolbar.total_label.setText(f"Total: ${retail_total:,.0f}M")
            if retail_mom is not None:
                self.toolbar.mom_label.setText(f"MoM: {retail_mom:+.1f}%")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        retail_df = self.slice_data(result.get("retail"))
        usrec_df = result.get("usrec")
        return (retail_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Retail Sales Settings"
