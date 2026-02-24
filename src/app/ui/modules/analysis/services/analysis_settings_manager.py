"""Analysis Settings Manager - Shared settings across all analysis modules."""

from typing import Dict, Any, List

from app.services.base_settings_manager import BaseSettingsManager


DEFAULT_TICKERS = [
    "AAPL",   # Apple - Technology
    "MSFT",   # Microsoft - Technology
    "GOOGL",  # Alphabet - Technology
    "AMZN",   # Amazon - Consumer Discretionary
    "NVDA",   # NVIDIA - Technology
    "META",   # Meta - Technology
    "BRK-B",  # Berkshire Hathaway - Financials
    "JPM",    # JPMorgan Chase - Financials
    "JNJ",    # Johnson & Johnson - Healthcare
    "V",      # Visa - Financials
    "PG",     # Procter & Gamble - Consumer Staples
    "UNH",    # UnitedHealth - Healthcare
    "HD",     # Home Depot - Consumer Discretionary
    "MA",     # Mastercard - Financials
    "XOM",    # Exxon Mobil - Energy
    "PFE",    # Pfizer - Healthcare
    "KO",     # Coca-Cola - Consumer Staples
    "PEP",    # PepsiCo - Consumer Staples
    "DIS",    # Disney - Communication Services
    "NFLX",   # Netflix - Communication Services
]


class AnalysisSettingsManager(BaseSettingsManager):
    """Shared settings for Efficient Frontier, Correlation, and Covariance modules."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "tickers": list(DEFAULT_TICKERS),
            "lookback_days": 1825,  # 5 years
            "num_simulations": 10000,
            "corr_decimals": 3,
            "cov_decimals": 4,
            "matrix_colorscale": "Green-Yellow-Red",
            "corr_fixed_color_scale": True,
            "show_matrix_overlay": True,
            "ef_show_gridlines": True,
            "ef_colorscale": "Magma",
            "ef_show_individual_securities": True,
            "ef_show_frontier": True,
            "ef_show_cml": True,
            "ef_show_max_sharpe": True,
            "ef_show_min_vol": True,
            "ef_show_max_sortino": True,
            "ef_show_indifference_curve": True,
            "ef_allow_leverage": True,
            "periodicity": "daily",
        }

    @property
    def settings_filename(self) -> str:
        return "analysis_settings.json"

    def get_tickers(self) -> List[str]:
        """Get the current ticker list."""
        return list(self.get_setting("tickers") or [])

    def set_tickers(self, tickers: List[str]) -> None:
        """Set the ticker list."""
        self.update_settings({"tickers": list(tickers)})

    def get_lookback_days(self) -> int:
        """Get the lookback period in calendar days."""
        return self.get_setting("lookback_days") or 1825

    def get_num_simulations(self) -> int:
        """Get the number of Monte Carlo simulations."""
        return self.get_setting("num_simulations") or 10000

    def get_corr_decimals(self) -> int:
        val = self.get_setting("corr_decimals")
        return val if val is not None else 3

    def set_corr_decimals(self, value: int) -> None:
        self.update_settings({"corr_decimals": value})

    def get_cov_decimals(self) -> int:
        val = self.get_setting("cov_decimals")
        return val if val is not None else 4

    def set_cov_decimals(self, value: int) -> None:
        self.update_settings({"cov_decimals": value})

    def get_periodicity(self) -> str:
        return self.get_setting("periodicity") or "daily"

    def set_periodicity(self, value: str) -> None:
        self.update_settings({"periodicity": value})

    def get_matrix_colorscale(self) -> str:
        return self.get_setting("matrix_colorscale") or "Green-Yellow-Red"

    def set_matrix_colorscale(self, value: str) -> None:
        self.update_settings({"matrix_colorscale": value})

    def get_corr_fixed_color_scale(self) -> bool:
        val = self.get_setting("corr_fixed_color_scale")
        return val if val is not None else True

    def set_corr_fixed_color_scale(self, value: bool) -> None:
        self.update_settings({"corr_fixed_color_scale": value})

    def get_show_matrix_overlay(self) -> bool:
        val = self.get_setting("show_matrix_overlay")
        return val if val is not None else True

    def get_ef_show_gridlines(self) -> bool:
        val = self.get_setting("ef_show_gridlines")
        return val if val is not None else True

    def get_ef_colorscale(self) -> str:
        return self.get_setting("ef_colorscale") or "Magma"

    def get_ef_show_individual_securities(self) -> bool:
        val = self.get_setting("ef_show_individual_securities")
        return val if val is not None else True
