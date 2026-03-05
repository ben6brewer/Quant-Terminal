"""GDP Module — Stacked components (Raw) or QoQ growth line (YoY %) with view toggle."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_MONTHS
from app.ui.modules.gdp.services import GdpFredService
from .widgets.gdp_toolbar import GdpToolbar
from .widgets.gdp_chart import GdpChart


class GdpModule(FredDataModule):
    """GDP module — dual-mode: stacked components (Raw) or growth line (YoY %)."""

    SETTINGS_FILENAME = "gdp_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
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

    def create_toolbar(self):
        return GdpToolbar(self.theme_manager)

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
            self.toolbar.update_info(
                real_gdp=stats.get("real_gdp"),
                gdp_growth=stats.get("gdp_growth"),
                quarter=stats.get("quarter"),
            )

    def extract_chart_data(self, result):
        comp_df = self.slice_data(result.get("components"))
        growth_df = self.slice_data(result.get("growth"))
        usrec_df = result.get("usrec")
        return (comp_df, growth_df, usrec_df)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({"view_mode": view})
        self._render()

    def _apply_extra_settings(self):
        self.toolbar.set_active_view(self.settings_manager.get_setting("view_mode"))

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
