"""Monthly Returns Settings Manager - Persistent display settings."""

from app.services.base_settings_manager import BaseSettingsManager


class MonthlyReturnsSettingsManager(BaseSettingsManager):
    """Settings manager for Monthly Returns module."""

    @property
    def DEFAULT_SETTINGS(self):
        return {
            "show_ytd": True,
            "use_gradient": True,
            "decimals": 2,
            "colorscale": "Red-Green",
        }

    @property
    def settings_filename(self):
        return "monthly_returns_settings.json"
