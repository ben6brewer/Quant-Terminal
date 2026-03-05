"""Payrolls Module - Stacked bar MoM sector payroll changes."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.labor_market.services import LaborMarketFredService
from .widgets.payrolls_toolbar import PayrollsToolbar
from .widgets.payrolls_chart import PayrollsChart


class PayrollsModule(FredDataModule):
    """Payrolls module — stacked bar MoM sector payroll changes from FRED."""

    SETTINGS_FILENAME = "payrolls_settings.json"
    DEFAULT_SETTINGS = {
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "show_recession_shading": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return PayrollsToolbar(self.theme_manager)

    def create_chart(self):
        return PayrollsChart()

    def get_fred_service(self):
        return LaborMarketFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching payrolls data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch payrolls data."

    def update_toolbar_info(self, result):
        stats = LaborMarketFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(payrolls_mom=stats.get("payrolls_mom"))

    def extract_chart_data(self, result):
        payrolls = self.slice_data(result.get("payroll_levels"))
        usrec = result.get("usrec")
        return (payrolls, usrec)

    def create_settings_dialog(self, current_settings):
        from .widgets.payrolls_settings_dialog import PayrollsSettingsDialog
        return PayrollsSettingsDialog(
            self.theme_manager,
            current_settings=current_settings,
            parent=self,
        )
