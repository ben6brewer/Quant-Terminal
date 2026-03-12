"""Housing Permits Module — Stacked area (Raw) or YoY% line with view toggle."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.housing.services import HousingFredService
from .widgets.housing_permits_chart import HousingPermitsChart


class HousingPermitsModule(FredDataModule):
    """Housing Permits module — dual-mode: stacked components (Raw) or YoY% line."""

    SETTINGS_FILENAME = "housing_permits_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_sf_permits": True,
        "show_multi_permits": True,
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
            stat_labels=[("permits_label", "Permits: --")],
        )

    def create_chart(self):
        return HousingPermitsChart()

    def get_fred_service(self):
        return HousingFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching housing permits data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch housing permits data."

    def update_toolbar_info(self, result):
        stats = HousingFredService.get_latest_stats(result)
        if stats:
            total_permits = stats.get("total_permits")
            if total_permits is not None:
                self.toolbar.permits_label.setText(f"Permits: {total_permits:.0f}K")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        permits_df = self.slice_data(result.get("permits"))
        usrec_df = result.get("usrec")
        return (permits_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_sf_permits", "Show Single-Family Permits"),
            ("show_multi_permits", "Show Multi-Family Permits"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Housing Permits Settings"
