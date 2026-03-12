"""Personal Income Module — Income levels with Nominal/Real toggle."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.income.services import IncomeFredService
from .widgets.personal_income_chart import PersonalIncomeChart


class PersonalIncomeModule(FredDataModule):
    """Personal Income module — income levels with Nominal/Real toggle."""

    SETTINGS_FILENAME = "personal_income_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "data_mode": "Nominal",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }
    VIEW_MODE = "view_mode"
    DATA_MODE = "data_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "YoY %"],
            data_mode_options=["Nominal", "Real"],
            stat_labels=[
                ("income_label", "PI: --"),
            ],
        )

    def create_chart(self):
        return PersonalIncomeChart()

    def get_fred_service(self):
        return IncomeFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching personal income data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch personal income data."

    def update_toolbar_info(self, result):
        stats = IncomeFredService.get_latest_stats(result)
        if stats:
            personal_income = stats.get("personal_income")
            if personal_income is not None:
                self.toolbar.income_label.setText(f"PI: ${personal_income:.2f}T")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        income_df = self.slice_data(result.get("income"))
        real_income_df = self.slice_data(result.get("real_income"))
        usrec_df = result.get("usrec")
        return (income_df, real_income_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Personal Income Settings"
