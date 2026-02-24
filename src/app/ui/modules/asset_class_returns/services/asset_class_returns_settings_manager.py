"""Asset Class Returns Settings Manager - Persistent display settings."""

from app.services.base_settings_manager import BaseSettingsManager


class AssetClassReturnsSettingsManager(BaseSettingsManager):
    """Settings manager for Asset Class Returns module."""

    @property
    def DEFAULT_SETTINGS(self):
        return {"decimals": 1, "label_mode": "label", "custom_tickers": [], "cagr_years": None, "show_cagr": True}

    @property
    def settings_filename(self):
        return "asset_class_returns_settings.json"
