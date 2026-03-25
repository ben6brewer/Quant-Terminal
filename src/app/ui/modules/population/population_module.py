"""Population Module — US population and working-age demographics."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from .services import PopulationFredService
from .widgets.population_chart import PopulationChart


class PopulationModule(FredDataModule):
    """Population module — total, working age, and civilian population."""

    SETTINGS_FILENAME = "population_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_total_pop": True,
        "show_working_age": True,
        "show_civilian": True,
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
            stat_labels=[('pop_label', 'Population: --'), ('working_label', 'Working Age: --')],
            lookback_options=['5Y', '10Y', '20Y', 'Max'],
            default_lookback_index=3,
        )

    def create_chart(self):
        return PopulationChart()

    def get_fred_service(self):
        return PopulationFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching population data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch population data."

    def update_toolbar_info(self, result):
        stats = PopulationFredService.get_latest_stats(result)
        if stats:
            pop = stats.get("population")
            if pop is not None:
                self.toolbar.pop_label.setText(f"Population: {pop:.1f}M")
            working = stats.get("working_age")
            if working is not None:
                self.toolbar.working_label.setText(f"Working Age: {working:.1f}M")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        import pandas as pd
        frames = [f for f in [result.get("pop_thousands"), result.get("pop_persons")] if f is not None]
        pop_df = self.slice_data(pd.concat(frames, axis=1)) if frames else None
        usrec_df = result.get("usrec")
        return (pop_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_total_pop", "Show Total Population"),
            ("show_working_age", "Show Working Age"),
            ("show_civilian", "Show Civilian Population"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Population Settings"
