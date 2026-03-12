"""GDP Module — Stacked components (Raw) or QoQ growth line (YoY %) with view toggle."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_MONTHS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.gdp.services import GdpFredService
from .widgets.gdp_chart import GdpChart


class GdpModule(FredDataModule):
    """GDP module — dual-mode: stacked components (Raw) or growth line (YoY %)."""

    SETTINGS_FILENAME = "gdp_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "data_mode": "Real",
        "show_pce": True,
        "show_investment": True,
        "show_government": True,
        "show_exports": True,
        "show_imports": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }
    VIEW_MODE = "view_mode"
    DATA_MODE = "data_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "YoY %"],
            data_mode_options=["Real", "Nominal"],
            stat_labels=[
                ("gdp_label", "Real GDP: --"),
                ("growth_label", "Growth: --"),
                ("quarter_label", "--"),
            ],
            lookback_options=["5Y", "10Y", "20Y", "Max"],
            default_lookback_index=1,
        )

    def create_chart(self):
        return GdpChart()

    def get_fred_service(self):
        return GdpFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching GDP data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch GDP data."

    def get_lookback_map(self):
        return LOOKBACK_MONTHS

    def update_toolbar_info(self, result):
        stats = GdpFredService.get_latest_stats(result)
        if stats:
            real_gdp = stats.get("real_gdp")
            gdp_growth = stats.get("gdp_growth")
            quarter = stats.get("quarter")
            if real_gdp is not None:
                self.toolbar.gdp_label.setText(f"Real GDP: ${real_gdp:.2f}T")
            if gdp_growth is not None:
                color = "#4CAF50" if gdp_growth >= 0 else "#EF5350"
                self.toolbar.growth_label.setText(f"Growth: {gdp_growth:+.1f}%")
                self.toolbar.growth_label.setStyleSheet(
                    self.toolbar.growth_label.styleSheet() + f"color: {color};"
                )
            if quarter is not None:
                self.toolbar.quarter_label.setText(quarter)
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        comp_df = self.slice_data(result.get("components"))
        nom_comp_df = self.slice_data(result.get("nominal_components"))
        growth_df = self.slice_data(result.get("growth"))
        gdp_df = self.slice_data(result.get("gdp"))
        usrec_df = result.get("usrec")
        return (comp_df, nom_comp_df, growth_df, gdp_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_pce", "Show PCE (Personal Consumption)"),
            ("show_investment", "Show Gross Private Investment"),
            ("show_government", "Show Government Spending"),
            ("show_exports", "Show Exports"),
            ("show_imports", "Show Imports"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "GDP Settings"
