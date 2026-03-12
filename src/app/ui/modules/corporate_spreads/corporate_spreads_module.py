"""Corporate Spreads Module — Multi-line: Baa-10Y, Aaa-10Y, HY OAS."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_DAYS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.financial_conditions.services import FinancialConditionsFredService
from .widgets.corporate_spreads_chart import CorporateSpreadsChart


class CorporateSpreadsModule(FredDataModule):
    """Corporate Spreads module — Baa/Aaa spreads + HY OAS from FRED."""

    SETTINGS_FILENAME = "corporate_spreads_settings.json"
    DEFAULT_SETTINGS = {
        "show_baa": True,
        "show_aaa": True,
        "show_hy": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            stat_labels=[("baa_label", "Baa: --"), ("hy_label", "HY OAS: --")],
        )

    def create_chart(self):
        return CorporateSpreadsChart()

    def get_fred_service(self):
        return FinancialConditionsFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching corporate spread data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch corporate spread data."

    def get_lookback_map(self):
        return LOOKBACK_DAYS

    def update_toolbar_info(self, result):
        stats = FinancialConditionsFredService.get_latest_stats(result)
        if stats:
            baa_spread = stats.get("baa_spread")
            hy_oas = stats.get("hy_oas")
            if baa_spread is not None:
                self.toolbar.baa_label.setText(f"Baa: {baa_spread:.2f}%")
            if hy_oas is not None:
                self.toolbar.hy_label.setText(f"HY OAS: {hy_oas:.0f}bp")
        self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        spreads_df = self.slice_data(result.get("spreads"))
        usrec_df = result.get("usrec")
        return (spreads_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_baa", "Show Baa-10Y Spread"),
            ("show_aaa", "Show Aaa-10Y Spread"),
            ("show_hy", "Show HY OAS"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Corporate Spreads Settings"
