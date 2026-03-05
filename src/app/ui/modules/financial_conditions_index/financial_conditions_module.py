"""Financial Conditions Module — NFCI multi-line with zero reference."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_WEEKS
from app.ui.modules.financial_conditions.services import FinancialConditionsFredService
from .widgets.financial_conditions_toolbar import FinancialConditionsToolbar
from .widgets.financial_conditions_chart import FinancialConditionsChart


class FinancialConditionsModule(FredDataModule):
    """Financial Conditions module — NFCI + subindices from FRED."""

    SETTINGS_FILENAME = "financial_conditions_settings.json"
    DEFAULT_SETTINGS = {
        "show_nfci": True,
        "show_adjusted": True,
        "show_credit": True,
        "show_leverage": True,
        "show_nonfin_leverage": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return FinancialConditionsToolbar(self.theme_manager)

    def create_chart(self):
        return FinancialConditionsChart()

    def get_fred_service(self):
        return FinancialConditionsFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching financial conditions data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch financial conditions data."

    def get_lookback_map(self):
        return LOOKBACK_WEEKS

    def update_toolbar_info(self, result):
        stats = FinancialConditionsFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                nfci=stats.get("nfci"),
                nfci_prev=stats.get("nfci_prev"),
            )

    def extract_chart_data(self, result):
        nfci_df = self.slice_data(result.get("nfci"))
        usrec_df = result.get("usrec")
        return (nfci_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_nfci", "Show NFCI"),
            ("show_adjusted", "Show Adjusted NFCI"),
            ("show_credit", "Show Credit Subindex"),
            ("show_leverage", "Show Leverage Subindex"),
            ("show_nonfin_leverage", "Show NonFin Leverage Subindex"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Financial Conditions Settings"
