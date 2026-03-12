"""ISM Manufacturing Module — Multi-line: PMI, New Orders, Employment with 50 threshold."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_MONTHS
from app.ui.modules.ism.services import IsmFredService
from .widgets.ism_manufacturing_toolbar import IsmManufacturingToolbar
from .widgets.ism_manufacturing_chart import IsmManufacturingChart


class IsmManufacturingModule(FredDataModule):
    """ISM Manufacturing module — PMI, New Orders, Employment from FRED."""

    SETTINGS_FILENAME = "ism_manufacturing_settings.json"
    DEFAULT_SETTINGS = {
        "show_pmi": True,
        "show_new_orders": True,
        "show_employment": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return IsmManufacturingToolbar(self.theme_manager)

    def create_chart(self):
        return IsmManufacturingChart()

    def get_fred_service(self):
        return IsmFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching ISM Manufacturing data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch ISM Manufacturing data."

    def get_lookback_map(self):
        return LOOKBACK_MONTHS

    def update_toolbar_info(self, result):
        stats = IsmFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(pmi=stats.get("pmi"))

    def extract_chart_data(self, result):
        mfg_df = self.slice_data(result.get("manufacturing"))
        usrec_df = result.get("usrec")
        return (mfg_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_pmi", "Show PMI"),
            ("show_new_orders", "Show New Orders"),
            ("show_employment", "Show Employment"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "ISM Manufacturing Settings"
