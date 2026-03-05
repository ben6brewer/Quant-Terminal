"""PPI Module - Producer Price Index visualization."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.inflation.services import InflationFredService
from .widgets.ppi_toolbar import PpiToolbar
from .widgets.ppi_chart import PpiChart


class PpiModule(FredDataModule):
    """PPI module — 4 PPI series YoY% from FRED."""

    SETTINGS_FILENAME = "ppi_settings.json"
    DEFAULT_SETTINGS = {
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
        "show_ppi_final_demand": True,
        "show_ppi_core": True,
        "show_ppi_energy": True,
        "show_ppi_services": True,
    }

    def create_toolbar(self):
        return PpiToolbar(self.theme_manager)

    def create_chart(self):
        return PpiChart()

    def get_fred_service(self):
        return InflationFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching PPI data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch PPI data."

    def update_toolbar_info(self, result):
        ppi_df = result.get("ppi")
        if ppi_df is not None and not ppi_df.empty and "PPI Final Demand" in ppi_df.columns:
            s = ppi_df["PPI Final Demand"].dropna()
            if not s.empty:
                self.toolbar.update_info(ppi_final=float(s.iloc[-1]))

    def extract_chart_data(self, result):
        return (self.slice_data(result.get("ppi")),)

    def get_settings_options(self):
        return [
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
            ("show_ppi_final_demand", "Show PPI Final Demand"),
            ("show_ppi_core", "Show PPI Core"),
            ("show_ppi_energy", "Show PPI Energy"),
            ("show_ppi_services", "Show PPI Services"),
        ]

    def get_settings_dialog_title(self):
        return "PPI Settings"
