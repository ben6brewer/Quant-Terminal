"""Consumer Credit Module — Dual-view: Raw $T levels or YoY% growth."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.credit.services import CreditFredService
from .widgets.consumer_credit_toolbar import ConsumerCreditToolbar
from .widgets.consumer_credit_chart import ConsumerCreditChart


class ConsumerCreditModule(FredDataModule):
    """Consumer Credit module — Raw levels ($T) or YoY% growth."""

    SETTINGS_FILENAME = "consumer_credit_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return ConsumerCreditToolbar(self.theme_manager)

    def create_chart(self):
        return ConsumerCreditChart()

    def get_fred_service(self):
        return CreditFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching consumer credit data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch consumer credit data."

    def update_toolbar_info(self, result):
        stats = CreditFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(total_credit=stats.get("total_credit"))

    def extract_chart_data(self, result):
        credit_df = self.slice_data(result.get("credit"))
        usrec_df = result.get("usrec")
        return (credit_df, usrec_df)

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
        return "Consumer Credit Settings"
