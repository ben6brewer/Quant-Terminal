"""ISM Services Module — Single-line: Services Activity with 50 threshold."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_MONTHS
from app.ui.modules.ism.services import IsmFredService
from .widgets.ism_services_toolbar import IsmServicesToolbar
from .widgets.ism_services_chart import IsmServicesChart


class IsmServicesModule(FredDataModule):
    """ISM Services module — Services Activity PMI from FRED."""

    SETTINGS_FILENAME = "ism_services_settings.json"
    DEFAULT_SETTINGS = {
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return IsmServicesToolbar(self.theme_manager)

    def create_chart(self):
        return IsmServicesChart()

    def get_fred_service(self):
        return IsmFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching ISM Services data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch ISM Services data."

    def get_lookback_map(self):
        return LOOKBACK_MONTHS

    def update_toolbar_info(self, result):
        stats = IsmFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(services=stats.get("services"))

    def extract_chart_data(self, result):
        svc_df = self.slice_data(result.get("services"))
        usrec_df = result.get("usrec")
        return (svc_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "ISM Services Settings"
