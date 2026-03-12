"""Metals Module — Multi-line: Gold, Silver, Copper, Platinum, Palladium (yfinance)."""

from app.ui.modules.yfinance_base_module import YFinanceDataModule
from app.ui.modules.fred_base_module import LOOKBACK_DAYS
from .services.metals_yfinance_service import MetalsYFinanceService
from .widgets.metals_toolbar import MetalsToolbar
from .widgets.metals_chart import MetalsChart


class MetalsModule(YFinanceDataModule):
    """Metals module — commodity metal futures from yfinance."""

    SETTINGS_FILENAME = "metals_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Normalized",
        "show_gold": True,
        "show_silver": True,
        "show_copper": True,
        "show_platinum": True,
        "show_palladium": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return MetalsToolbar(self.theme_manager)

    def create_chart(self):
        return MetalsChart()

    def get_data_service(self):
        return MetalsYFinanceService.fetch_all_data

    def get_loading_message(self):
        return "Fetching metals data from Yahoo Finance..."

    def get_fail_message(self):
        return "Failed to fetch metals data."

    def get_lookback_map(self):
        return LOOKBACK_DAYS

    def update_toolbar_info(self, result):
        stats = MetalsYFinanceService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                gold=stats.get("gold"),
                silver=stats.get("silver"),
                copper=stats.get("copper"),
                platinum=stats.get("platinum"),
                palladium=stats.get("palladium"),
            )

    def extract_chart_data(self, result):
        metals_df = self.slice_data(result.get("metals"))
        return (metals_df,)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({"view_mode": view})
        self._render()

    def _apply_extra_settings(self):
        self.toolbar.set_active_view(self.settings_manager.get_setting("view_mode"))

    def get_settings_options(self):
        return [
            ("show_gold", "Show Gold"),
            ("show_silver", "Show Silver"),
            ("show_copper", "Show Copper"),
            ("show_platinum", "Show Platinum"),
            ("show_palladium", "Show Palladium"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Metals Settings"
