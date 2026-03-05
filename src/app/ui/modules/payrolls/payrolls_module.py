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

    def get_settings_options(self):
        return [
            ("show_gridlines", "Show Gridlines"),
            ("show_crosshair", "Show Crosshair"),
            ("show_legend", "Show Legend"),
            ("show_hover_tooltip", "Show Hover Tooltip"),
            ("show_recession_shading", "Show NBER Recession Shading"),
        ]

    def get_settings_dialog_title(self):
        return "Payrolls Settings"
