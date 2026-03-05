"""Demographics Module - Unemployment rates by race and gender."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.labor_market.services import LaborMarketFredService
from .widgets.demographics_toolbar import DemographicsToolbar
from .widgets.demographics_chart import DemographicsChart


class DemographicsModule(FredDataModule):
    """Demographics module — unemployment rates by race and gender from FRED."""

    SETTINGS_FILENAME = "demographics_settings.json"
    DEFAULT_SETTINGS = {
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "show_recession_shading": True,
        "demo_series": ["White", "Black", "Hispanic"],
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return DemographicsToolbar(self.theme_manager)

    def create_chart(self):
        return DemographicsChart()

    def get_fred_service(self):
        return LaborMarketFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching demographics data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch demographics data."

    def update_toolbar_info(self, result):
        rates_df = result.get("rates")
        if rates_df is not None and not rates_df.empty:
            date_str = rates_df.index[-1].strftime("%b %Y")
            self.toolbar.update_info(date_str=date_str)

    def extract_chart_data(self, result):
        rates = self.slice_data(result.get("rates"))
        usrec = result.get("usrec")
        return (rates, usrec)

    def create_settings_dialog(self, current_settings):
        from .widgets.demographics_settings_dialog import DemographicsSettingsDialog
        return DemographicsSettingsDialog(
            self.theme_manager,
            current_settings=current_settings,
            parent=self,
        )
