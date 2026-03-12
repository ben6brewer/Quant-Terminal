"""Fed Balance Sheet Module — Total assets line or breakdown stacked area."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_WEEKS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.monetary_policy.services import MonetaryFredService
from .widgets.fed_balance_sheet_chart import FedBalanceSheetChart


class FedBalanceSheetModule(FredDataModule):
    """Fed Balance Sheet module — total assets or stacked area breakdown."""

    SETTINGS_FILENAME = "fed_balance_sheet_settings.json"
    DEFAULT_SETTINGS = {
        "show_breakdown": False,
        "show_treasuries": True,
        "show_mbs": True,
        "show_agency_debt": True,
        "show_loans": True,
        "show_other": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return FredToolbar(self.theme_manager,
                           stat_labels=[("assets_label", "Total Assets: --")],
                           default_lookback_index=3)

    def create_chart(self):
        return FedBalanceSheetChart()

    def get_fred_service(self):
        return MonetaryFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching Fed balance sheet data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch Fed balance sheet data."

    def get_lookback_map(self):
        return LOOKBACK_WEEKS

    def update_toolbar_info(self, result):
        bs_df = result.get("balance_sheet")
        if bs_df is not None and not bs_df.empty and "Total Assets" in bs_df.columns:
            latest = bs_df["Total Assets"].dropna()
            if not latest.empty:
                total_assets = float(latest.iloc[-1])
                self.toolbar.assets_label.setText(f"Total Assets: ${total_assets:.2f}T")
        self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        bs_df = self.slice_data(result.get("balance_sheet"))
        usrec_df = result.get("usrec")
        return (bs_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_breakdown", "Show breakdown (Treasuries/MBS/Agency/Loans/Other)"),
            ("show_treasuries", "Show Treasuries"),
            ("show_mbs", "Show MBS"),
            ("show_agency_debt", "Show Agency Debt"),
            ("show_loans", "Show Loans"),
            ("show_other", "Show Other"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Fed Balance Sheet Settings"
