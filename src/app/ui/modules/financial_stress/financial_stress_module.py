"""Financial Stress Module — Multi-line: STLFSI + KCFSI."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_WEEKS
from app.ui.modules.stress.services import StressFredService
from .widgets.financial_stress_toolbar import FinancialStressToolbar
from .widgets.financial_stress_chart import FinancialStressChart


class FinancialStressModule(FredDataModule):
    """Financial Stress module — STLFSI + KCFSI from FRED."""

    SETTINGS_FILENAME = "financial_stress_settings.json"
    DEFAULT_SETTINGS = {
        "show_stlfsi": True,
        "show_kcfsi": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return FinancialStressToolbar(self.theme_manager)

    def create_chart(self):
        return FinancialStressChart()

    def get_fred_service(self):
        return StressFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching financial stress data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch financial stress data."

    def get_lookback_map(self):
        return LOOKBACK_WEEKS

    def update_toolbar_info(self, result):
        stats = StressFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                stlfsi=stats.get("stlfsi"),
                kcfsi=stats.get("kcfsi"),
            )

    def extract_chart_data(self, result):
        stress_df = self.slice_data(result.get("stress"))
        usrec_df = result.get("usrec")
        return (stress_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_stlfsi", "Show STLFSI"),
            ("show_kcfsi", "Show KCFSI"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Financial Stress Settings"
