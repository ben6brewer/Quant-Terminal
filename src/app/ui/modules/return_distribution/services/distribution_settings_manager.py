"""Distribution Settings Manager - Manages return distribution settings with persistence."""

from __future__ import annotations

from typing import Dict, Any

from app.services.base_settings_manager import BaseSettingsManager


class DistributionSettingsManager(BaseSettingsManager):
    """
    Manages return distribution module settings with persistent storage.

    Settings:
    - exclude_cash: If True, FREE CASH is excluded from return calculations
    """

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        """Default distribution settings."""
        return {
            "exclude_cash": True,  # Default: exclude cash from returns
            "show_kde_curve": True,  # KDE smooth line overlay
            "show_normal_distribution": True,  # Normal distribution overlay
            "show_mean_median_lines": True,  # Mean/median vertical lines
            "show_cdf_view": False,  # CDF instead of histogram
        }

    @property
    def settings_filename(self) -> str:
        """Settings file name."""
        return "distribution_settings.json"
