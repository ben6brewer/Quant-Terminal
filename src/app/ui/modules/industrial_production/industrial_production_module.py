"""Industrial Production Module — IP Index, Manufacturing, Capacity Utilization."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.gdp.services import GdpFredService
from .widgets.industrial_production_toolbar import IndustrialProductionToolbar
from .widgets.industrial_production_chart import IndustrialProductionChart


class IndustrialProductionModule(FredDataModule):
    """Industrial Production module — 3 lines: IP Index, Manufacturing, Capacity Utilization."""

    SETTINGS_FILENAME = "industrial_production_settings.json"
    DEFAULT_SETTINGS = {
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
        "show_industrial_production": True,
        "show_manufacturing": True,
        "show_capacity_utilization": True,
    }

    def create_toolbar(self):
        return IndustrialProductionToolbar(self.theme_manager)

    def create_chart(self):
        return IndustrialProductionChart()

    def get_fred_service(self):
        return GdpFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching industrial production data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch industrial production data."

    def update_toolbar_info(self, result):
        stats = GdpFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                ip_index=stats.get("ip_index"),
                capacity_util=stats.get("capacity_util"),
            )

    def extract_chart_data(self, result):
        prod_df = self.slice_data(result.get("production"))
        cap_df = self.slice_data(result.get("capacity"))
        return (prod_df, cap_df)

    def get_settings_options(self):
        return [
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
            ("show_industrial_production", "Show Industrial Production"),
            ("show_manufacturing", "Show Manufacturing"),
            ("show_capacity_utilization", "Show Capacity Utilization"),
        ]

    def get_settings_dialog_title(self):
        return "Industrial Production Settings"
