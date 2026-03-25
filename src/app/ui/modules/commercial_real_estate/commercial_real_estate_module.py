"""Commercial Real Estate Module — CRE prices and loan data."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.fred_toolbar import FredToolbar
from .services import CreFredService
from .widgets.commercial_real_estate_chart import CommercialRealEstateChart


class CommercialRealEstateModule(FredDataModule):
    """Commercial Real Estate module — CRE indices and loan volumes."""

    SETTINGS_FILENAME = "commercial_real_estate_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_cre_prices": True,
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
            view_options=["Raw", "YoY %"],
            stat_labels=[("cre_label", "CRE Index: --")],
            lookback_options=["5Y", "10Y", "20Y", "Max"],
            default_lookback_index=3,
        )

    def create_chart(self):
        return CommercialRealEstateChart()

    def get_fred_service(self):
        return CreFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching commercial real estate data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch CRE data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def update_toolbar_info(self, result):
        stats = CreFredService.get_latest_stats(result)
        if stats:
            cre = stats.get("cre_index")
            if cre is not None:
                self.toolbar.cre_label.setText(f"CRE Index: {cre:.1f}")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        cre_df = self.slice_data(result.get("cre"))
        usrec_df = result.get("usrec")
        return (cre_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_cre_prices", "Show CRE Prices"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Commercial Real Estate Settings"
