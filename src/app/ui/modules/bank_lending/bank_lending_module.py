"""Bank Lending Module — Dual-view: Raw stacked area ($B) or YoY% multi-line."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_WEEKS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.banking.services import BankingFredService
from .widgets.bank_lending_chart import BankLendingChart


class BankLendingModule(FredDataModule):
    """Bank Lending module — dual-mode: Raw ($B) or YoY% from FRED."""

    SETTINGS_FILENAME = "bank_lending_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_ci": True,
        "show_real_estate": True,
        "show_consumer": True,
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
            stat_labels=[("total_label", "Total: --")],
            default_lookback_index=3,
        )

    def create_chart(self):
        return BankLendingChart()

    def get_fred_service(self):
        return BankingFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching bank lending data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch bank lending data."

    def get_lookback_map(self):
        return LOOKBACK_WEEKS

    def update_toolbar_info(self, result):
        stats = BankingFredService.get_latest_stats(result)
        if stats:
            total_loans = stats.get("total_loans")
            if total_loans is not None:
                self.toolbar.total_label.setText(f"Total: ${total_loans:,.0f}B")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        loans_df = self.slice_data(result.get("loans"))
        usrec_df = result.get("usrec")
        return (loans_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_ci", "Show C&I Loans"),
            ("show_real_estate", "Show Real Estate"),
            ("show_consumer", "Show Consumer"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Bank Lending Settings"
