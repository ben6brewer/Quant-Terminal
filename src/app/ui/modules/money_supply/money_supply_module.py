"""Money Supply Module — M1 and M2 money supply levels or YoY% from FRED."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.monetary_policy.services import MonetaryFredService
from .widgets.money_supply_toolbar import MoneySupplyToolbar
from .widgets.money_supply_chart import MoneySupplyChart


class MoneySupplyModule(FredDataModule):
    """M1 + M2 money supply module with YoY% toggle and recession shading."""

    SETTINGS_FILENAME = "money_supply_settings.json"
    DEFAULT_SETTINGS = {
        "show_m1": True,
        "show_m2": True,
        "view_mode": "Raw",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return MoneySupplyToolbar(self.theme_manager)

    def create_chart(self):
        return MoneySupplyChart()

    def get_fred_service(self):
        return MonetaryFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching money supply data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch money supply data."

    def update_toolbar_info(self, result):
        supply_df = result.get("money_supply")
        if supply_df is not None and not supply_df.empty and "M2" in supply_df.columns:
            latest = supply_df["M2"].dropna()
            if not latest.empty:
                self.toolbar.update_info(m2=float(latest.iloc[-1]))

    def extract_chart_data(self, result):
        supply_df = self.slice_data(result.get("money_supply"))
        usrec_df = result.get("usrec")
        return (supply_df, usrec_df)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({"view_mode": view})
        self._render()

    def _apply_extra_settings(self):
        self.toolbar.set_active_view(self.settings_manager.get_setting("view_mode"))

    def get_settings_options(self):
        return [
            ("show_m1", "Show M1"),
            ("show_m2", "Show M2"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Money Supply Settings"
