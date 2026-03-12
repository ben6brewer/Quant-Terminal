"""Reserve Balances Module — Bank reserves at the Fed with optional Total Assets overlay."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_WEEKS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.monetary_policy.services import MonetaryFredService
from .widgets.reserve_balances_chart import ReserveBalancesChart


class ReserveBalancesModule(FredDataModule):
    """Reserve Balances module — bank reserves at Fed from FRED."""

    SETTINGS_FILENAME = "reserve_balances_settings.json"
    DEFAULT_SETTINGS = {
        "show_total_assets_overlay": False,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return FredToolbar(self.theme_manager,
                           stat_labels=[("reserves_label", "Reserves: --")],
                           default_lookback_index=5)

    def create_chart(self):
        return ReserveBalancesChart()

    def get_fred_service(self):
        return MonetaryFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching reserve balance data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch reserve balance data."

    def get_lookback_map(self):
        return LOOKBACK_WEEKS

    def update_toolbar_info(self, result):
        res_df = result.get("reserves")
        if res_df is not None and not res_df.empty and "Reserve Balances" in res_df.columns:
            latest = res_df["Reserve Balances"].dropna()
            if not latest.empty:
                reserves = float(latest.iloc[-1])
                self.toolbar.reserves_label.setText(f"Reserves: ${reserves:.2f}T")
        self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        res_df = self.slice_data(result.get("reserves"))
        bs_df = self.slice_data(result.get("balance_sheet"))
        usrec_df = result.get("usrec")
        return (res_df, bs_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_total_assets_overlay", "Show Total Assets"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Reserve Balances Settings"
