"""Money Velocity Module — M2 velocity (quarterly) with recession shading."""

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_QUARTERS
from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.monetary_policy.services import MonetaryFredService
from .widgets.money_velocity_chart import MoneyVelocityChart


class MoneyVelocityModule(FredDataModule):
    """M2 Velocity module — quarterly ratio from FRED with recession shading."""

    SETTINGS_FILENAME = "money_velocity_settings.json"
    DEFAULT_SETTINGS = {
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return FredToolbar(self.theme_manager,
                           stat_labels=[("m2v_label", "M2V: --")],
                           lookback_options=["5Y", "10Y", "20Y", "Max"],
                           default_lookback_index=3)

    def create_chart(self):
        return MoneyVelocityChart()

    def get_fred_service(self):
        return MonetaryFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching M2 velocity data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch M2 velocity data."

    def get_lookback_map(self):
        return LOOKBACK_QUARTERS

    def update_toolbar_info(self, result):
        vel_df = result.get("velocity")
        if vel_df is not None and not vel_df.empty and "M2 Velocity" in vel_df.columns:
            latest = vel_df["M2 Velocity"].dropna()
            if not latest.empty:
                m2v = float(latest.iloc[-1])
                self.toolbar.m2v_label.setText(f"M2V: {m2v:.2f}")
        self.toolbar._update_timestamp()

    def extract_chart_data(self, result):
        vel_df = self.slice_data(result.get("velocity"))
        usrec_df = result.get("usrec")
        return (vel_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Money Velocity Settings"
