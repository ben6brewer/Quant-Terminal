"""Trade Balance Module — Dual-view: Raw (exports/imports lines) or YoY% balance."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.trade.services import TradeFredService
from .widgets.trade_balance_toolbar import TradeBalanceToolbar
from .widgets.trade_balance_chart import TradeBalanceChart


class TradeBalanceModule(FredDataModule):
    """Trade Balance module — dual-mode: Raw or YoY%."""

    SETTINGS_FILENAME = "trade_balance_settings.json"
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
        return TradeBalanceToolbar(self.theme_manager)

    def create_chart(self):
        return TradeBalanceChart()

    def get_fred_service(self):
        return TradeFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching trade balance data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch trade balance data."

    def update_toolbar_info(self, result):
        stats = TradeFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                balance=stats.get("balance"),
                balance_chg=stats.get("balance_chg"),
            )

    def extract_chart_data(self, result):
        trade_df = self.slice_data(result.get("trade"))
        usrec_df = result.get("usrec")
        return (trade_df, usrec_df)

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
        return "Trade Balance Settings"
