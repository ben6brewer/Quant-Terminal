"""Household Debt Module — Dual-view: Raw debt, % GDP, Debt Service, YoY."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.household.services import HouseholdFredService
from .widgets.household_debt_chart import HouseholdDebtChart


class HouseholdDebtModule(FredDataModule):
    """Household Debt module — debt level, debt-to-GDP%, debt service%, or YoY%."""

    SETTINGS_FILENAME = "household_debt_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
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
            view_options=["Raw", "% GDP", "Debt Service", "YoY"],
            stat_labels=[("debt_label", "Debt: --"), ("gdp_label", "Debt/GDP: --")],
            lookback_options=["5Y", "10Y", "20Y", "Max"],
            default_lookback_index=3,
        )

    def create_chart(self):
        return HouseholdDebtChart()

    def get_fred_service(self):
        return HouseholdFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching household debt data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch household debt data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def update_toolbar_info(self, result):
        stats = HouseholdFredService.get_latest_stats(result)
        if stats:
            household_debt = stats.get("household_debt")
            debt_to_gdp = stats.get("debt_to_gdp")
            if household_debt is not None:
                self.toolbar.debt_label.setText(f"Debt: ${household_debt:.1f}T")
            if debt_to_gdp is not None:
                self.toolbar.gdp_label.setText(f"Debt/GDP: {debt_to_gdp:.1f}%")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        debt_raw_df = self.slice_data(result.get("household_debt"))
        debt_ratios_df = self.slice_data(result.get("debt"))
        usrec_df = result.get("usrec")
        return (debt_raw_df, debt_ratios_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Household Debt Settings"
