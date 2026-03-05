"""Government Debt Module — Dual-view: Raw debt level or Debt/GDP %."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.fiscal.services import FiscalFredService
from .widgets.government_debt_toolbar import GovernmentDebtToolbar
from .widgets.government_debt_chart import GovernmentDebtChart


class GovernmentDebtModule(FredDataModule):
    """Government Debt module — debt level or debt-to-GDP%."""

    SETTINGS_FILENAME = "government_debt_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return GovernmentDebtToolbar(self.theme_manager)

    def create_chart(self):
        return GovernmentDebtChart()

    def get_fred_service(self):
        return FiscalFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching government debt data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch government debt data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def update_toolbar_info(self, result):
        stats = FiscalFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                debt_trillions=stats.get("debt_trillions"),
                debt_gdp_pct=stats.get("debt_gdp_pct"),
            )

    def extract_chart_data(self, result):
        debt_df = self.slice_data(result.get("debt"))
        debt_gdp_df = self.slice_data(result.get("debt_gdp"))
        usrec_df = result.get("usrec")
        return (debt_df, debt_gdp_df, usrec_df)

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
        return "Government Debt Settings"
