"""Factor Models Settings Manager — persistent settings."""

from typing import Dict, Any

from app.services.base_settings_manager import BaseSettingsManager


class FactorSettingsManager(BaseSettingsManager):
    """Settings for the Factor Models module."""

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "input_mode": "ticker",
            "ticker": "",
            "portfolio": "",
            "model_key": "ff5mom",
            "frequency": "monthly",
            "lookback_days": 1825,
            "custom_start_date": None,
            "custom_end_date": None,
            # Display settings
            "show_goodness_of_fit": True,
            "show_diagnostics": True,
            "show_col_coefficient": True,
            "show_col_std_error": True,
            "show_col_t_stat": True,
            "show_col_p_value": True,
            "show_col_ci": True,
            "show_only_significant": False,
            "confidence_level": 0.95,
        }

    @property
    def settings_filename(self) -> str:
        return "factor_models_settings.json"
