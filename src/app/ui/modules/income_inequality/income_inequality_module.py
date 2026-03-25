"""Income Inequality Module — GINI index and median incomes."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.wealth_inequality.services import WealthInequalityFredService
from .widgets.income_inequality_chart import IncomeInequalityChart

LOOKBACK_YEARS = {
    "10Y": 10, "20Y": 20, "30Y": 30, "Max": None,
}


class IncomeInequalityModule(FredDataModule):
    """Income Inequality module — GINI index and median household/personal income."""

    SETTINGS_FILENAME = "income_inequality_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_hh_income": True,
        "show_personal_income": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }
    VIEW_MODE = "view_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "YoY %"],
            stat_labels=[("hh_income_label", "HH Income: --")],
            lookback_options=["10Y", "20Y", "30Y", "Max"],
            default_lookback_index=3,
        )

    def create_chart(self):
        return IncomeInequalityChart()

    def get_fred_service(self):
        return WealthInequalityFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching income inequality data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch income inequality data."

    def get_lookback_map(self):
        return LOOKBACK_YEARS

    def update_toolbar_info(self, result):
        stats = WealthInequalityFredService.get_latest_stats(result)
        if stats:
            hh = stats.get("hh_income")
            if hh is not None:
                self.toolbar.hh_income_label.setText(f"HH Income: ${hh:,.0f}")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        incomes_df = self.slice_data(result.get("incomes"))
        usrec_df = result.get("usrec")
        return (incomes_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_hh_income", "Show Median HH Income"),
            ("show_personal_income", "Show Median Personal Income"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Income Inequality Settings"
