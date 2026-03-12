"""Trade Balance Module — Dual-view: Raw (exports/imports lines) or YoY% balance."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.trade.services import TradeFredService
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
    VIEW_MODE = "view_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "YoY %"],
            stat_labels=[("balance_label", "Balance: --")],
            default_lookback_index=3,
        )

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
            balance = stats.get("balance")
            if balance is not None:
                self.toolbar.balance_label.setText(f"Balance: ${balance:,.1f}B")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        trade_df = self.slice_data(result.get("trade"))
        usrec_df = result.get("usrec")
        return (trade_df, usrec_df)

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
