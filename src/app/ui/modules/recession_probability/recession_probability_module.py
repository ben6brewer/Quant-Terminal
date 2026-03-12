"""Recession Probability Module — Single-line RECPROUSM156N chart."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_MONTHS
from app.ui.modules.recession.services import RecessionFredService
from .widgets.recession_probability_toolbar import RecessionProbabilityToolbar
from .widgets.recession_probability_chart import RecessionProbabilityChart


class RecessionProbabilityModule(FredDataModule):
    """Recession Probability module — RECPROUSM156N line from FRED."""

    SETTINGS_FILENAME = "recession_probability_settings.json"
    DEFAULT_SETTINGS = {
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return RecessionProbabilityToolbar(self.theme_manager)

    def create_chart(self):
        return RecessionProbabilityChart()

    def get_fred_service(self):
        return RecessionFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching recession probability data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch recession probability data."

    def get_lookback_map(self):
        return LOOKBACK_MONTHS

    def update_toolbar_info(self, result):
        stats = RecessionFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(recession_prob=stats.get("recession_prob"))

    def extract_chart_data(self, result):
        recession_df = result.get("recession")
        if recession_df is not None and "Recession Prob" in recession_df.columns:
            prob_df = self.slice_data(recession_df[["Recession Prob"]])
        else:
            prob_df = None
        usrec_df = result.get("usrec")
        return (prob_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Recession Probability Settings"
