"""Currency Module — Dollar Index multi-line with Raw / YoY% toggle."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_DAYS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.currency.services import CurrencyFredService
from .widgets.currency_chart import CurrencyChart


class CurrencyModule(FredDataModule):
    """Currency module — Dollar Index + Adv. Economies from FRED."""

    SETTINGS_FILENAME = "currency_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_dollar_index": True,
        "show_adv_economies": True,
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
            stat_labels=[("dollar_label", "DXY: --"), ("eur_label", "EUR: --")],
        )

    def create_chart(self):
        return CurrencyChart()

    def get_fred_service(self):
        return CurrencyFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching currency data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch currency data."

    def get_lookback_map(self):
        return LOOKBACK_DAYS

    def update_toolbar_info(self, result):
        stats = CurrencyFredService.get_latest_stats(result)
        if stats:
            dollar_index = stats.get("dollar_index")
            eur = stats.get("eur")
            if dollar_index is not None:
                self.toolbar.dollar_label.setText(f"DXY: {dollar_index:.1f}")
            if eur is not None:
                self.toolbar.eur_label.setText(f"EUR: {eur:.4f}")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        dollar_df = self.slice_data(result.get("dollar_index"))
        usrec_df = result.get("usrec")
        return (dollar_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_dollar_index", "Show Dollar Index"),
            ("show_adv_economies", "Show Adv. Economies"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Currency Settings"
