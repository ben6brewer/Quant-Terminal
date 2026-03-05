"""Vehicle Sales Module — Multi-line: Total, Light Autos, Heavy Trucks."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.retail.services import RetailFredService
from .widgets.vehicle_sales_toolbar import VehicleSalesToolbar
from .widgets.vehicle_sales_chart import VehicleSalesChart


class VehicleSalesModule(FredDataModule):
    """Vehicle Sales module — multi-line chart with recession bands."""

    SETTINGS_FILENAME = "vehicle_sales_settings.json"
    DEFAULT_SETTINGS = {
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

    def create_toolbar(self):
        return VehicleSalesToolbar(self.theme_manager)

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
            self.toolbar.update_info(vehicle_total=stats.get("vehicle_total"))

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
