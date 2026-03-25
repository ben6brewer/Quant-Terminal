"""Home Sales Module — Existing and new home sales with supply months."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.home_market.services import HomeMarketFredService
from .widgets.home_sales_chart import HomeSalesChart


class HomeSalesModule(FredDataModule):
    """Home Sales module — sales volume and months of supply."""

    SETTINGS_FILENAME = "home_sales_settings.json"
    DEFAULT_SETTINGS = {
        "view_mode": "Raw",
        "show_existing_sales": True,
        "show_new_sales": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_legend": True,
        "show_hover_tooltip": True,
        "lookback": "10Y",
    }
    VIEW_MODE = "view_mode"

    def create_toolbar(self):
        return FredToolbar(
            self.theme_manager,
            view_options=["Raw", "YoY %"],
            stat_labels=[("existing_label", "Existing: --"), ("new_label", "New: --")],
            default_lookback_index=3,
        )

    def create_chart(self):
        return HomeSalesChart()

    def get_fred_service(self):
        return HomeMarketFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching home sales data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch home sales data."

    def update_toolbar_info(self, result):
        stats = HomeMarketFredService.get_latest_stats(result)
        if stats:
            existing = stats.get("existing")
            if existing is not None:
                self.toolbar.existing_label.setText(f"Existing: {existing:,.0f}K")
            new = stats.get("new")
            if new is not None:
                self.toolbar.new_label.setText(f"New: {new:,.0f}K")
            self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        import pandas as pd
        frames = [f for f in [result.get("sales_existing"), result.get("sales_new")] if f is not None]
        sales_df = self.slice_data(pd.concat(frames, axis=1)) if frames else None
        usrec_df = result.get("usrec")
        return (sales_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_existing_sales", "Show Existing Home Sales"),
            ("show_new_sales", "Show New Home Sales"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_legend", "Show legend"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Home Sales Settings"
