"""Credit Conditions Module — Dual-view: Delinquency rates or Credit levels."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.credit.services import CreditFredService
from .widgets.credit_conditions_toolbar import CreditConditionsToolbar
from .widgets.credit_conditions_chart import CreditConditionsChart


class CreditConditionsModule(FredDataModule):
    """Credit Conditions module — delinquency rates or consumer credit levels."""

    SETTINGS_FILENAME = "credit_conditions_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Delinquency",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return CreditConditionsToolbar(self.theme_manager)

    def create_chart(self):
        return CreditConditionsChart()

    def get_fred_service(self):
        return CreditFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching credit data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch credit data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def get_lookback_options(self):
        return ["5Y", "10Y", "20Y", "Max"]

    def update_toolbar_info(self, result):
        stats = CreditFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                cc_delinquency=stats.get("cc_delinquency"),
                total_credit=stats.get("total_credit"),
            )

    def extract_chart_data(self, result):
        delinq_df = self.slice_data(result.get("delinquency"))
        credit_df = self.slice_data(result.get("credit"))
        usrec_df = result.get("usrec")
        return (delinq_df, credit_df, usrec_df)

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
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Credit Conditions Settings"
