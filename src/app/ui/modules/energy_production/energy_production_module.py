"""Energy Production Module — Oil/gas extraction, crude stocks, propane."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from .services import EnergyProductionFredService
from .widgets.energy_production_chart import EnergyProductionChart


class EnergyProductionModule(FredDataModule):
    """Energy Production module — production indices and inventory levels."""

    SETTINGS_FILENAME = "energy_production_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_mining": True,
        "show_wti": True,
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
            stat_labels=[('extraction_label', 'Extraction: --')],
            lookback_options=['1Y', '2Y', '5Y', '10Y', '20Y', 'Max'],
            default_lookback_index=3,
        )

    def create_chart(self):
        return EnergyProductionChart()

    def get_fred_service(self):
        return EnergyProductionFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching energy production data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch energy production data."

    def update_toolbar_info(self, result):
        stats = EnergyProductionFredService.get_latest_stats(result)
        if stats:
            extraction = stats.get("extraction")
            if extraction is not None:
                self.toolbar.extraction_label.setText(f"Extraction: {extraction:.1f}")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        prod_df = self.slice_data(result.get("production"))
        usrec_df = result.get("usrec")
        return (prod_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_mining", "Show Mining Production"),
            ("show_wti", "Show WTI Crude"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Energy Production Settings"
