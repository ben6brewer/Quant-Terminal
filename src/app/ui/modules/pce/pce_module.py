"""PCE Module - Personal Consumption Expenditures inflation."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.inflation.services import InflationFredService
from .widgets.pce_toolbar import PceToolbar
from .widgets.pce_chart import PceChart


class PceModule(FredDataModule):
    """PCE module — PCE and Core PCE YoY% from FRED."""

    SETTINGS_FILENAME = "pce_settings.json"
    DEFAULT_SETTINGS = {
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "show_reference_line": True,
        "show_recession_shading": False,
        "lookback": "5Y",
        "show_pce": True,
        "show_core_pce": True,
    }

    def create_toolbar(self):
        return PceToolbar(self.theme_manager)

    def create_chart(self):
        return PceChart()

    def get_fred_service(self):
        return InflationFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching PCE data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch PCE data."

    def update_toolbar_info(self, result):
        stats = InflationFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(pce=stats.get("pce"))

    def extract_chart_data(self, result):
        return (self.slice_data(result.get("pce")),)

    def get_settings_options(self):
        return [
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
            ("show_reference_line", "Show 2% reference line"),
            ("show_pce", "Show PCE"),
            ("show_core_pce", "Show Core PCE"),
        ]

    def get_settings_dialog_title(self):
        return "PCE Settings"
