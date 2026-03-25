"""Supply Chain Module — Inventory/sales ratios."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from .services import SupplyChainFredService
from .widgets.supply_chain_chart import SupplyChainChart


class SupplyChainModule(FredDataModule):
    """Supply Chain module — inventory/sales ratio tracking."""

    SETTINGS_FILENAME = "supply_chain_settings.json"
    DEFAULT_SETTINGS = {
        "show_total_is": True,
        "show_retail_is": True,
        "show_mfg_is": True,
        "show_wholesale_is": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,

            stat_labels=[('total_label', 'Total I/S: --')],
            lookback_options=['1Y', '2Y', '5Y', '10Y', '20Y', 'Max'],
            default_lookback_index=3,
        )

    def create_chart(self):
        return SupplyChainChart()

    def get_fred_service(self):
        return SupplyChainFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching inventory data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch inventory data."

    def update_toolbar_info(self, result):
        stats = SupplyChainFredService.get_latest_stats(result)
        if stats:
            total = stats.get("total_is")
            if total is not None:
                self.toolbar.total_label.setText(f"Total I/S: {total:.3f}")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        inv_df = self.slice_data(result.get("inventories"))
        usrec_df = result.get("usrec")
        return (inv_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_total_is", "Show Total I/S Ratio"),
            ("show_retail_is", "Show Retail I/S"),
            ("show_mfg_is", "Show Manufacturing I/S"),
            ("show_wholesale_is", "Show Wholesale I/S"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Supply Chain Settings"
