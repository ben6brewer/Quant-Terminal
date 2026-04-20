"""Unemployment by Age Module — NSA unemployment rates by age group."""

from app.ui.modules.fred_base_module import FredDataModule
from .services import UnemploymentAgeService
from .widgets.unemployment_age_toolbar import UnemploymentAgeToolbar
from .widgets.unemployment_age_chart import UnemploymentAgeChart

_DEFAULT_AGE_SERIES = ["16+", "20-24", "25-34", "35-44", "45-54", "55-64", "65+"]


class UnemploymentAgeModule(FredDataModule):
    """Unemployment by Age module — NSA rates for 11 BLS age brackets."""

    SETTINGS_FILENAME = "unemployment_age_settings.json"
    DEFAULT_SETTINGS = {
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "show_recession_shading": True,
        "age_series": _DEFAULT_AGE_SERIES,
        "lookback": "20Y",
    }

    def create_toolbar(self):
        return UnemploymentAgeToolbar(self.theme_manager)

    def create_chart(self):
        return UnemploymentAgeChart()

    def get_fred_service(self):
        return UnemploymentAgeService.fetch_all_data

    def get_loading_message(self):
        return "Fetching unemployment by age data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch unemployment by age data."

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
        from .widgets.unemployment_age_settings_dialog import UnemploymentAgeSettingsDialog
        return UnemploymentAgeSettingsDialog(
            self.theme_manager,
            current_settings=current_settings,
            parent=self,
        )
