"""Labor Market Overview Module - Full UNRATE history with optional U-6 overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict

from PySide6.QtWidgets import QVBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule
from app.ui.modules.labor_market.services import LaborMarketFredService
from .services.labor_market_overview_settings_manager import LaborMarketOverviewSettingsManager
from .widgets.labor_market_overview_toolbar import LaborMarketOverviewToolbar
from .widgets.labor_market_overview_chart import LaborMarketOverviewChart

if TYPE_CHECKING:
    import pandas as pd


LOOKBACK_MONTHS = {
    "1Y": 12,
    "2Y": 24,
    "5Y": 60,
    "10Y": 120,
    "20Y": 240,
    "Max": None,
}


class LaborMarketOverviewModule(BaseModule):
    """Unemployment Rate module — full U-3 history with optional U-6 and recession shading."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        self.settings_manager = LaborMarketOverviewSettingsManager()
        self._data_initialized = False
        self._data: Optional[Dict] = None
        self._current_lookback = self.settings_manager.get_setting("lookback")

        self._setup_ui()
        self._connect_signals()
        self._apply_settings()
        self._apply_theme()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = LaborMarketOverviewToolbar(self.theme_manager)
        layout.addWidget(self.toolbar)

        self.chart = LaborMarketOverviewChart()
        layout.addWidget(self.chart, stretch=1)

    def _connect_signals(self):
        self.toolbar.home_clicked.connect(self.home_clicked.emit)
        self.toolbar.lookback_changed.connect(self._on_lookback_changed)
        self.toolbar.settings_clicked.connect(self._on_settings_clicked)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._data_initialized:
            self._data_initialized = True
            self._initialize_data()

    def hideEvent(self, event):
        self._cancel_worker()
        super().hideEvent(event)

    # ── Data Loading ──────────────────────────────────────────────────────────

    def _initialize_data(self):
        from app.services.fred_api_key_service import FredApiKeyService

        if not FredApiKeyService.has_api_key():
            self._show_api_key_dialog()
        else:
            self._fetch_data()

    def _show_api_key_dialog(self):
        from app.ui.widgets.common.api_key_dialog import APIKeyDialog
        from app.services.fred_api_key_service import FredApiKeyService

        dialog = APIKeyDialog(self.theme_manager, parent=self)
        if dialog.exec():
            key = dialog.get_api_key()
            if key:
                FredApiKeyService.set_api_key(key)
                self._fetch_data()
        else:
            self.chart.show_placeholder(
                "FRED API key required.\nSet your key in Settings > API Keys."
            )

    def _fetch_data(self):
        self._run_worker(
            LaborMarketFredService.fetch_all_data,
            loading_message="Fetching unemployment data from FRED...",
            on_complete=self._on_data_fetched,
            on_error=self._on_fetch_error,
        )

    def _on_data_fetched(self, result):
        self._hide_loading()
        self._cleanup_worker()

        if result is None:
            self.chart.show_placeholder("Failed to fetch unemployment data.")
            return

        self._data = result

        stats = LaborMarketFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(unrate=stats.get("unrate"))

        self._render()

    def _on_fetch_error(self, error_msg: str):
        self._hide_loading()
        self._cleanup_worker()
        self.chart.show_placeholder(f"Error fetching data: {error_msg}")

    # ── Render ────────────────────────────────────────────────────────────────

    def _slice_monthly(self, df: "Optional[pd.DataFrame]") -> "Optional[pd.DataFrame]":
        if df is None or df.empty:
            return df
        months = LOOKBACK_MONTHS.get(self._current_lookback)
        if months is None:
            return df
        return df.tail(months)

    def _render(self):
        if self._data is None:
            return
        settings = self.settings_manager.get_all_settings()
        rates = self._slice_monthly(self._data.get("rates"))
        usrec = self._data.get("usrec")
        self.chart.update_data(rates, usrec, settings)

    def _on_lookback_changed(self, lookback: str):
        self._current_lookback = lookback
        self.settings_manager.update_settings({"lookback": lookback})
        self._render()

    # ── Settings ──────────────────────────────────────────────────────────────

    def _on_settings_clicked(self):
        from PySide6.QtWidgets import QDialog
        from .widgets.labor_market_overview_settings_dialog import LaborMarketOverviewSettingsDialog

        dialog = LaborMarketOverviewSettingsDialog(
            self.theme_manager,
            current_settings=self.settings_manager.get_all_settings(),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if new_settings:
                self.settings_manager.update_settings(new_settings)
                self._render()

    def _apply_settings(self):
        lookback = self.settings_manager.get_setting("lookback")
        self._current_lookback = lookback
        self.toolbar.set_active_lookback(lookback)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        super()._apply_theme()
        self.chart.set_theme(self.theme_manager.current_theme)
