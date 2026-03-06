"""Retail Sales Module — Dual-view: Raw two-line or YoY% growth."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.retail.services import RetailFredService
from .widgets.retail_sales_toolbar import RetailSalesToolbar
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

    def create_toolbar(self):
        return RetailSalesToolbar(self.theme_manager)

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
            self.toolbar.update_info(
                retail_total=stats.get("retail_total"),
                retail_mom=stats.get("retail_mom"),
            )

    def extract_chart_data(self, result):
        retail_df = self.slice_data(result.get("retail"))
        usrec_df = result.get("usrec")
        return (retail_df, usrec_df)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)
        self.toolbar.data_mode_changed.connect(self._on_data_mode_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({"view_mode": view})
        self._render()

    def _on_data_mode_changed(self, mode: str):
        self.settings_manager.update_settings({"data_mode": mode})
        self._render()

    def _apply_extra_settings(self):
        self.toolbar.set_active_view(self.settings_manager.get_setting("view_mode"))
        self.toolbar.set_active_data_mode(self.settings_manager.get_setting("data_mode"))

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
