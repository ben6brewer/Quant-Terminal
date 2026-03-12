"""Vehicle Sales Module — Dual-view: Raw multi-line or YoY% multi-line."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.retail.services import RetailFredService
from .widgets.vehicle_sales_chart import VehicleSalesChart


class VehicleSalesModule(FredDataModule):
    """Vehicle Sales module — dual-view: Raw multi-line or YoY% multi-line."""

    SETTINGS_FILENAME = "vehicle_sales_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_total": True,
        "show_light_autos": True,
        "show_heavy_trucks": True,
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
            stat_labels=[("total_label", "Total: --")],
        )

    def create_chart(self):
        return VehicleSalesChart()

    def get_fred_service(self):
        return RetailFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching vehicle sales data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch vehicle sales data."

    def update_toolbar_info(self, result):
        stats = RetailFredService.get_latest_stats(result)
        if stats:
            vehicle_total = stats.get("vehicle_total")
            if vehicle_total is not None:
                self.toolbar.total_label.setText(f"Total: {vehicle_total:.1f}M SAAR")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        vehicles_df = self.slice_data(result.get("vehicles"))
        usrec_df = result.get("usrec")
        return (vehicles_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_total", "Show Total Vehicle Sales"),
            ("show_light_autos", "Show Light Autos"),
            ("show_heavy_trucks", "Show Heavy Trucks"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Vehicle Sales Settings"
