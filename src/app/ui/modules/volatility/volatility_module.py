"""Volatility Module — Multi-line: VIX, NASDAQ Vol, MOVE + 5 more vol indices."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_DAYS
from app.ui.modules.volatility_index.services import VolatilityFredService
from .widgets.volatility_toolbar import VolatilityToolbar
from .widgets.volatility_chart import VolatilityChart


class VolatilityModule(FredDataModule):
    """Volatility module — VIX + 3M Vol + Oil Vol from FRED."""

    SETTINGS_FILENAME = "volatility_settings.json"
    DEFAULT_SETTINGS = {
        "show_vix": True,
        "show_3m_vol": False,
        "show_oil_vol": False,
        "show_nasdaq_vol": False,
        "show_russell_vol": False,
        "show_djia_vol": False,
        "show_em_vol": False,
        "show_move": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "show_thresholds": True,
        "threshold_1": 20,
        "threshold_2": 30,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return VolatilityToolbar(self.theme_manager)

    def create_chart(self):
        return VolatilityChart()

    def get_fred_service(self):
        return VolatilityFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching volatility data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch volatility data."

    def get_lookback_map(self):
        return LOOKBACK_DAYS

    def update_toolbar_info(self, result):
        stats = VolatilityFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                vix=stats.get("vix"),
                move=stats.get("move"),
            )

    def extract_chart_data(self, result):
        vol_df = self.slice_data(result.get("volatility"))
        usrec_df = result.get("usrec")
        return (vol_df, usrec_df)

    def get_settings_options(self):
        return []

    def create_settings_dialog(self, current_settings):
        from .widgets.volatility_settings_dialog import VolatilitySettingsDialog
        return VolatilitySettingsDialog(
            self.theme_manager,
            current_settings=current_settings,
            parent=self,
        )
