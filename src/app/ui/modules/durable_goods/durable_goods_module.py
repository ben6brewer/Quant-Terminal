"""Durable Goods Module — Dual-view: Raw multi-line or YoY% growth."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.manufacturing.services import ManufacturingFredService
from .widgets.durable_goods_toolbar import DurableGoodsToolbar
from .widgets.durable_goods_chart import DurableGoodsChart


class DurableGoodsModule(FredDataModule):
    """Durable Goods module — raw levels or YoY% growth."""

    SETTINGS_FILENAME = "durable_goods_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return DurableGoodsToolbar(self.theme_manager)

    def create_chart(self):
        return DurableGoodsChart()

    def get_fred_service(self):
        return ManufacturingFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching durable goods data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch durable goods data."

    def update_toolbar_info(self, result):
        stats = ManufacturingFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(dg_mom=stats.get("dg_mom"))

    def extract_chart_data(self, result):
        orders_df = self.slice_data(result.get("orders"))
        usrec_df = result.get("usrec")
        return (orders_df, usrec_df)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({"view_mode": view})
        self._render()

    def _apply_extra_settings(self):
        self.toolbar.set_active_view(self.settings_manager.get_setting("view_mode"))

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Durable Goods Settings"
