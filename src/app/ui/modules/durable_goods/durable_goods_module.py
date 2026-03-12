"""Durable Goods Module — Dual-view: Raw multi-line or YoY% growth."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.manufacturing.services import ManufacturingFredService
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
    VIEW_MODE = "view_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "YoY %"],
            stat_labels=[("mom_label", "MoM: --")],
        )

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
            dg_mom = stats.get("dg_mom")
            if dg_mom is not None:
                self.toolbar.mom_label.setText(f"MoM: {dg_mom:+.1f}%")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        orders_df = self.slice_data(result.get("orders"))
        usrec_df = result.get("usrec")
        return (orders_df, usrec_df)

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
