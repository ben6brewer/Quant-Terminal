"""Fed Funds Rate Module — EFFR history with target band and recession shading."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.ui.modules.fred_base_module import FredDataModule, LOOKBACK_MONTHS
from app.ui.modules.monetary_policy.services import MonetaryFredService
from .widgets.fed_funds_rate_toolbar import FedFundsRateToolbar
from .widgets.fed_funds_rate_chart import FedFundsRateChart

if TYPE_CHECKING:
    import pandas as pd


class FedFundsRateModule(FredDataModule):
    """Fed Funds Rate module — full EFFR history from FRED."""

    SETTINGS_FILENAME = "fed_funds_rate_settings.json"
    DEFAULT_SETTINGS = {
        "show_target_band": True,
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_hover_tooltip": True,
        "lookback": "Max",
    }

    def create_toolbar(self):
        return FedFundsRateToolbar(self.theme_manager)

    def create_chart(self):
        return FedFundsRateChart()

    def get_fred_service(self):
        return MonetaryFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching Fed funds rate data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch Fed funds rate data."

    def update_toolbar_info(self, result):
        effr_df = result.get("effr")
        if effr_df is not None and not effr_df.empty and "Fed Funds Rate" in effr_df.columns:
            latest = effr_df["Fed Funds Rate"].dropna()
            if not latest.empty:
                self.toolbar.update_info(effr=float(latest.iloc[-1]))

    def slice_data(self, df: "Optional[pd.DataFrame]") -> "Optional[pd.DataFrame]":
        """DateOffset-based slicing for mixed-frequency EFFR data."""
        if df is None or df.empty:
            return df
        months = LOOKBACK_MONTHS.get(self._current_lookback)
        if months is None:
            return df
        import pandas as pd
        cutoff = df.index.max() - pd.DateOffset(months=months)
        return df[df.index >= cutoff]

    def extract_chart_data(self, result):
        effr_df = self.slice_data(result.get("effr"))
        usrec_df = result.get("usrec")
        return (effr_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_target_band", "Show target range band (post-2008)"),
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Fed Funds Rate Settings"
