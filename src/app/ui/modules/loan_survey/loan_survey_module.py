"""Loan Survey (SLOOS) Module — Senior Loan Officer Opinion Survey."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.fred_toolbar import FredToolbar
from .services import LoanSurveyFredService
from .widgets.loan_survey_chart import LoanSurveyChart


class LoanSurveyModule(FredDataModule):
    """Loan Survey module — lending standards across categories."""

    SETTINGS_FILENAME = "loan_survey_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "All Standards",
        "show_ci_large": True,
        "show_ci_small": True,
        "show_credit_cards": True,
        "show_mortgages": True,
        "show_auto_loans": True,
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
            view_options=['All Standards', 'By Category'],
            stat_labels=[('ci_label', 'C&I Large: --'), ('cc_label', 'Credit Card: --')],
            lookback_options=['5Y', '10Y', '20Y', 'Max'],
            default_lookback_index=2,
        )

    def create_chart(self):
        return LoanSurveyChart()

    def get_fred_service(self):
        return LoanSurveyFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching SLOOS data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch SLOOS data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def update_toolbar_info(self, result):
        stats = LoanSurveyFredService.get_latest_stats(result)
        if stats:
            ci = stats.get("ci_large")
            if ci is not None:
                self.toolbar.ci_label.setText(f"C&I Large: {ci:+.1f}%")
            cc = stats.get("credit_card")
            if cc is not None:
                self.toolbar.cc_label.setText(f"Credit Card: {cc:+.1f}%")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        standards_df = self.slice_data(result.get("standards"))
        usrec_df = result.get("usrec")
        return (standards_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_ci_large", "Show C&I Large Firms"),
            ("show_ci_small", "Show C&I Small Firms"),
            ("show_credit_cards", "Show Credit Cards"),
            ("show_mortgages", "Show Mortgages"),
            ("show_auto_loans", "Show Auto Loans"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Loan Survey Settings"
