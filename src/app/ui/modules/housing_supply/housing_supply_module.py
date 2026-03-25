"""Housing Supply Module — Months of supply for new and existing homes."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.home_market.services import HomeMarketFredService
from .widgets.housing_supply_chart import HousingSupplyChart


class HousingSupplyModule(FredDataModule):
    """Housing Supply module — months of inventory for new and existing homes."""

    SETTINGS_FILENAME = "housing_supply_settings.json"
    DEFAULT_SETTINGS = {
        "show_new_supply": True,
        "show_existing_supply": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            stat_labels=[("new_supply_label", "New: --"), ("existing_supply_label", "Existing: --")],
            default_lookback_index=3,
        )

    def create_chart(self):
        return HousingSupplyChart()

    def get_fred_service(self):
        return HomeMarketFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching housing supply data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch housing supply data."

    def update_toolbar_info(self, result):
        stats = HomeMarketFredService.get_latest_stats(result)
        if stats:
            new_supply = stats.get("new_supply")
            if new_supply is not None:
                self.toolbar.new_supply_label.setText(f"New: {new_supply:.1f}mo")
            supply = stats.get("supply")
            if supply is not None:
                self.toolbar.existing_supply_label.setText(f"Existing: {supply:.1f}mo")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        supply_df = self.slice_data(result.get("supply"))
        usrec_df = result.get("usrec")
        return (supply_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_new_supply", "Show New Supply Months"),
            ("show_existing_supply", "Show Existing Supply Months"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Housing Supply Settings"
