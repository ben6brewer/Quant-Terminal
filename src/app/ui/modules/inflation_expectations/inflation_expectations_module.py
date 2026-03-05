"""Inflation Expectations Module - Market breakevens and consumer surveys."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.inflation.services import InflationFredService
from .widgets.inflation_expectations_toolbar import InflationExpectationsToolbar
from .widgets.inflation_expectations_chart import InflationExpectationsChart


class InflationExpectationsModule(FredDataModule):
    """Inflation Expectations — 5Y/10Y breakevens + Michigan 1Y survey from FRED."""

    SETTINGS_FILENAME = "inflation_expectations_settings.json"
    DEFAULT_SETTINGS = {
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "show_reference_line": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return InflationExpectationsToolbar(self.theme_manager)

    def create_chart(self):
        return InflationExpectationsChart()

    def get_fred_service(self):
        return InflationFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching inflation expectations from FRED..."

    def get_fail_message(self):
        return "Failed to fetch inflation expectations data."

    def update_toolbar_info(self, result):
        exp_df = result.get("expectations")
        if exp_df is not None and not exp_df.empty and "5Y Breakeven" in exp_df.columns:
            s = exp_df["5Y Breakeven"].dropna()
            if not s.empty:
                self.toolbar.update_info(breakeven_5y=float(s.iloc[-1]))

    def extract_chart_data(self, result):
        return (self.slice_data(result.get("expectations")),)

    def get_settings_options(self):
        return [
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
            ("show_reference_line", "Show 2% reference line"),
        ]

    def get_settings_dialog_title(self):
        return "Inflation Expectations Settings"
