"""Student Loans Module — Total and federal student loan balances."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.fred_toolbar import FredToolbar
from .services import StudentLoansFredService
from .widgets.student_loans_chart import StudentLoansChart


class StudentLoansModule(FredDataModule):
    """Student Loans module — outstanding student loan debt tracking."""

    SETTINGS_FILENAME = "student_loans_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_total_loans": True,
        "show_federal_loans": True,
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
            view_options=['Raw', 'YoY %'],
            stat_labels=[('total_label', 'Total: --'), ('federal_label', 'Federal: --')],
            lookback_options=['5Y', '10Y', '20Y', 'Max'],
            default_lookback_index=2,
        )

    def create_chart(self):
        return StudentLoansChart()

    def get_fred_service(self):
        return StudentLoansFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching student loan data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch student loan data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def update_toolbar_info(self, result):
        stats = StudentLoansFredService.get_latest_stats(result)
        if stats:
            total = stats.get("total")
            if total is not None:
                self.toolbar.total_label.setText(f"Total: ${total:.2f}T")
            federal = stats.get("federal")
            if federal is not None:
                self.toolbar.federal_label.setText(f"Federal: ${federal:.2f}T")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        loans_df = self.slice_data(result.get("loans"))
        usrec_df = result.get("usrec")
        return (loans_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_total_loans", "Show Total Student Loans"),
            ("show_federal_loans", "Show Federal Student Loans"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Student Loans Settings"
