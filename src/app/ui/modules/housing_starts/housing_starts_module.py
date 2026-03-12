"""Housing Starts Module — Stacked area (Raw) or YoY% line with view toggle."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.housing.services import HousingFredService
from .widgets.housing_starts_chart import HousingStartsChart


class HousingStartsModule(FredDataModule):
    """Housing Starts module — dual-mode: stacked components (Raw) or YoY% line."""

    SETTINGS_FILENAME = "housing_starts_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_sf": True,
        "show_multi": True,
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
            stat_labels=[("starts_label", "Starts: --")],
        )

    def create_chart(self):
        return HousingStartsChart()

    def get_fred_service(self):
        return HousingFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching housing starts data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch housing starts data."

    def update_toolbar_info(self, result):
        stats = HousingFredService.get_latest_stats(result)
        if stats:
            total_starts = stats.get("total_starts")
            if total_starts is not None:
                self.toolbar.starts_label.setText(f"Starts: {total_starts:.0f}K")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        starts_df = self.slice_data(result.get("starts"))
        usrec_df = result.get("usrec")
        return (starts_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_sf", "Show Single-Family Starts"),
            ("show_multi", "Show 5+ Unit Starts"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Housing Starts Settings"
