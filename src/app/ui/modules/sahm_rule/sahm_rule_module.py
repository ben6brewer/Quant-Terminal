"""Sahm Rule Module — Single-line SAHMCURRENT chart with 0.50 threshold."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_MONTHS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.recession.services import RecessionFredService
from .widgets.sahm_rule_chart import SahmRuleChart


class SahmRuleModule(FredDataModule):
    """Sahm Rule module — SAHMCURRENT line with 0.50 threshold from FRED."""

    SETTINGS_FILENAME = "sahm_rule_settings.json"
    DEFAULT_SETTINGS = {
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_hover_tooltip": True,
        "show_threshold": True,
        "threshold_value": 0.50,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            stat_labels=[("sahm_label", "Sahm: --")],
            default_lookback_index=5,
        )

    def create_chart(self):
        return SahmRuleChart()

    def get_fred_service(self):
        return RecessionFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching Sahm Rule data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch Sahm Rule data."

    def get_lookback_map(self):
        return LOOKBACK_MONTHS

    def update_toolbar_info(self, result):
        stats = RecessionFredService.get_latest_stats(result)
        if stats:
            sahm = stats.get("sahm")
            if sahm is not None:
                self.toolbar.sahm_label.setText(f"Sahm: {sahm:.2f}")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        recession_df = result.get("recession")
        if recession_df is not None and "Sahm Rule" in recession_df.columns:
            sahm_df = self.slice_data(recession_df[["Sahm Rule"]])
        else:
            sahm_df = None
        usrec_df = result.get("usrec")
        return (sahm_df, usrec_df)

    def get_settings_options(self):
        return []

    def create_settings_dialog(self, current_settings):
        from .widgets.sahm_rule_settings_dialog import SahmRuleSettingsDialog
        return SahmRuleSettingsDialog(
            self.theme_manager,
            current_settings=current_settings,
            parent=self,
        )
