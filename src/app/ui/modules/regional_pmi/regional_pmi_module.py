"""Regional PMI Module — Regional Fed manufacturing surveys."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from .services import RegionalPmiFredService
from .widgets.regional_pmi_chart import RegionalPmiChart


class RegionalPmiModule(FredDataModule):
    """Regional PMI module — Empire State, Philly, Dallas."""

    SETTINGS_FILENAME = "regional_pmi_settings.json"
    DEFAULT_SETTINGS = {
        "show_empire": True,
        "show_philly": True,
        "show_dallas": True,
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

            stat_labels=[('empire_label', 'Empire: --'), ('philly_label', 'Philly: --')],
            lookback_options=['1Y', '2Y', '5Y', '10Y', '20Y', 'Max'],
            default_lookback_index=2,
        )

    def create_chart(self):
        return RegionalPmiChart()

    def get_fred_service(self):
        return RegionalPmiFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching regional PMI data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch regional PMI data."

    def update_toolbar_info(self, result):
        stats = RegionalPmiFredService.get_latest_stats(result)
        if stats:
            empire = stats.get("empire")
            if empire is not None:
                self.toolbar.empire_label.setText(f"Empire: {empire:+.1f}")
            philly = stats.get("philly")
            if philly is not None:
                self.toolbar.philly_label.setText(f"Philly: {philly:+.1f}")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        regional_df = self.slice_data(result.get("regional"))
        usrec_df = result.get("usrec")
        return (regional_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_empire", "Show Empire State"),
            ("show_philly", "Show Philly Fed"),
            ("show_dallas", "Show Dallas Fed"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Regional PMI Settings"
