"""Government Debt Module — Dual-view: Raw debt level or Debt/GDP %."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.fiscal.services import FiscalFredService
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
    VIEW_MODE = "view_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "% GDP", "YoY", "Debt/GDP YoY"],
            stat_labels=[("debt_label", "Debt: --"), ("gdp_label", "Debt/GDP: --")],
            lookback_options=["5Y", "10Y", "20Y", "Max"],
            default_lookback_index=3,
        )

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
            debt_trillions = stats.get("debt_trillions")
            debt_gdp_pct = stats.get("debt_gdp_pct")
            if debt_trillions is not None:
                self.toolbar.debt_label.setText(f"Debt: ${debt_trillions:.1f}T")
            if debt_gdp_pct is not None:
                self.toolbar.gdp_label.setText(f"Debt/GDP: {debt_gdp_pct:.1f}%")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        debt_df = self.slice_data(result.get("debt"))
        debt_gdp_df = self.slice_data(result.get("debt_gdp"))
        usrec_df = result.get("usrec")
        return (debt_df, debt_gdp_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Government Debt Settings"
