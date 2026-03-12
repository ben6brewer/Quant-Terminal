"""Household Wealth Module — Net Worth ($T) with Raw/YoY% toggle."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.household.services import HouseholdFredService
from .widgets.household_wealth_toolbar import HouseholdWealthToolbar
from .widgets.household_wealth_chart import HouseholdWealthChart


class HouseholdWealthModule(FredDataModule):
    """Household Wealth module — Net Worth from FRED (quarterly)."""

    SETTINGS_FILENAME = "household_wealth_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return HouseholdWealthToolbar(self.theme_manager)

    def create_chart(self):
        return HouseholdWealthChart()

    def get_fred_service(self):
        return HouseholdFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching household wealth data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch household wealth data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def update_toolbar_info(self, result):
        stats = HouseholdFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(net_worth=stats.get("net_worth"))

    def extract_chart_data(self, result):
        wealth_df = self.slice_data(result.get("wealth"))
        usrec_df = result.get("usrec")
        return (wealth_df, usrec_df)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({"view_mode": view})
        self._render()

    def _apply_extra_settings(self):
        self.toolbar.set_active_view(self.settings_manager.get_setting("view_mode"))

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Household Wealth Settings"
