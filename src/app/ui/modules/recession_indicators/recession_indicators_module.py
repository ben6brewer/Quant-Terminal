"""Recession Indicators Module — Multi-line: Recession Probability + Sahm Rule."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_MONTHS
from app.ui.modules.recession.services import RecessionFredService
from .widgets.recession_indicators_toolbar import RecessionIndicatorsToolbar
from .widgets.recession_indicators_chart import RecessionIndicatorsChart


class RecessionIndicatorsModule(FredDataModule):
    """Recession Indicators module — Recession Probability + Sahm Rule from FRED."""

    SETTINGS_FILENAME = "recession_indicators_settings.json"
    DEFAULT_SETTINGS = {
        "show_recession_prob": True,
        "show_sahm": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return RecessionIndicatorsToolbar(self.theme_manager)

    def create_chart(self):
        return RecessionIndicatorsChart()

    def get_fred_service(self):
        return RecessionFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching recession indicator data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch recession indicator data."

    def get_lookback_map(self):
        return LOOKBACK_MONTHS

    def update_toolbar_info(self, result):
        stats = RecessionFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                recession_prob=stats.get("recession_prob"),
                sahm=stats.get("sahm"),
            )

    def extract_chart_data(self, result):
        recession_df = self.slice_data(result.get("recession"))
        usrec_df = result.get("usrec")
        return (recession_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_prob", "Show Recession Probability"),
            ("show_sahm", "Show Sahm Rule"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Recession Indicators Settings"
