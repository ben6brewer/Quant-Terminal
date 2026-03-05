"""Personal Income Module — Dual-view: Income levels or Savings Rate."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.income.services import IncomeFredService
from .widgets.personal_income_toolbar import PersonalIncomeToolbar
from .widgets.personal_income_chart import PersonalIncomeChart


class PersonalIncomeModule(FredDataModule):
    """Personal Income module — income levels or savings rate."""

    SETTINGS_FILENAME = "personal_income_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Income",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return PersonalIncomeToolbar(self.theme_manager)

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
            self.toolbar.update_info(
                savings_rate=stats.get("savings_rate"),
                personal_income=stats.get("personal_income"),
            )

    def extract_chart_data(self, result):
        income_df = self.slice_data(result.get("income"))
        savings_df = self.slice_data(result.get("savings"))
        usrec_df = result.get("usrec")
        return (income_df, savings_df, usrec_df)

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
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Personal Income Settings"
