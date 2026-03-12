"""Natural Gas Module — Single-line: Henry Hub Natural Gas."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_DAYS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.commodities.services import CommodityFredService
from .widgets.natural_gas_chart import NaturalGasChart


class NaturalGasModule(FredDataModule):
    """Natural Gas module — Henry Hub Natural Gas from FRED."""

    SETTINGS_FILENAME = "natural_gas_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }
    VIEW_MODE = "view_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "YoY %"],
            stat_labels=[("natgas_label", "NatGas: --")],
        )

    def create_chart(self):
        return NaturalGasChart()

    def get_fred_service(self):
        return CommodityFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching natural gas data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch natural gas data."

    def get_lookback_map(self):
        return LOOKBACK_DAYS

    def update_toolbar_info(self, result):
        stats = CommodityFredService.get_latest_stats(result)
        if stats:
            natgas = stats.get("natgas")
            if natgas is not None:
                self.toolbar.natgas_label.setText(f"NatGas: ${natgas:.2f}")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        energy_df = self.slice_data(result.get("energy"))
        if energy_df is not None:
            cols = [c for c in ["Natural Gas"] if c in energy_df.columns]
            energy_df = energy_df[cols] if cols else energy_df
        usrec_df = result.get("usrec")
        return (energy_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Natural Gas Settings"
