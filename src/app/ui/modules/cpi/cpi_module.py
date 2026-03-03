"""CPI Module - Consumer Price Index visualization with headline and breakdown views."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QVBoxLayout, QStackedWidget

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule

from app.ui.modules.inflation.services import InflationFredService
from .services.cpi_settings_manager import CpiSettingsManager
from .widgets.cpi_toolbar import CpiToolbar
from .widgets.cpi_headline_chart import CpiHeadlineChart
from .widgets.cpi_component_breakdown_chart import CpiComponentBreakdownChart

if TYPE_CHECKING:
    import pandas as pd

# Lookback period to number of months mapping
LOOKBACK_MONTHS = {
    "1Y": 12,
    "2Y": 24,
    "5Y": 60,
    "10Y": 120,
    "20Y": 240,
    "Max": None,
}


class CpiModule(BaseModule):
    """CPI module - Consumer Price Index visualization from FRED data."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        # Settings
        self.settings_manager = CpiSettingsManager()

        # State
        self._data_initialized = False
        self._yoy_df: Optional["pd.DataFrame"] = None
        self._current_lookback = "2Y"

        self._setup_ui()
        self._connect_signals()
        self._apply_settings()
        self._apply_theme()

    def _setup_ui(self):
        """Setup module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = CpiToolbar(self.theme_manager)
        layout.addWidget(self.toolbar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # View 0: Headline CPI
        self.headline_view = CpiHeadlineChart()
        self.stack.addWidget(self.headline_view)

        # View 1: Component Breakdown
        self.breakdown_view = CpiComponentBreakdownChart()
        self.stack.addWidget(self.breakdown_view)

    def _connect_signals(self):
        """Connect signals to slots."""
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

    def _initialize_data(self):
        """Check for API key and start data fetch."""
        from app.services.fred_api_key_service import FredApiKeyService

        if not FredApiKeyService.has_api_key():
            self._show_api_key_dialog()
        else:
            self._fetch_data()

    def _show_api_key_dialog(self):
        """Show the FRED API key dialog."""
        from app.ui.widgets.common.api_key_dialog import APIKeyDialog
        from app.services.fred_api_key_service import FredApiKeyService

        dialog = APIKeyDialog(self.theme_manager, parent=self)
        if dialog.exec():
            key = dialog.get_api_key()
            if key:
                FredApiKeyService.set_api_key(key)
                self._fetch_data()
        else:
            self.headline_view.show_placeholder(
                "FRED API key required for CPI data.\n"
                "Set your key in Settings > API Keys."
            )

    def _fetch_data(self):
        """Fetch all inflation data in background thread."""
        self._run_worker(
            InflationFredService.fetch_all_data,
            loading_message="Fetching CPI data from FRED...",
            on_complete=self._on_data_fetched,
            on_error=self._on_fetch_error,
        )

    def _on_data_fetched(self, result):
        """Handle successful data fetch."""
        self._hide_loading()
        self._cleanup_worker()

        if result is None:
            self.headline_view.show_placeholder("Failed to fetch CPI data.")
            self.breakdown_view.show_placeholder("Failed to fetch CPI data.")
            return

        # InflationFredService returns a dict; "cpi" key holds YoY% DataFrame
        cpi_df = result.get("cpi")
        if cpi_df is None or cpi_df.empty:
            self.headline_view.show_placeholder("Failed to fetch CPI data.")
            self.breakdown_view.show_placeholder("Failed to fetch CPI data.")
            return

        self._yoy_df = cpi_df

        # Update toolbar info
        stats = InflationFredService.get_latest_stats(result)
        if stats and "headline_cpi" in stats:
            self.toolbar.update_info(
                headline=stats["headline_cpi"],
                date_str=stats.get("date", ""),
            )

        # Push data to current view
        self._update_all_views()

    def _on_fetch_error(self, error_msg: str):
        """Handle fetch error."""
        self._hide_loading()
        self._cleanup_worker()
        self.headline_view.show_placeholder(f"Error fetching CPI data: {error_msg}")
        self.breakdown_view.show_placeholder(f"Error fetching CPI data: {error_msg}")

    def _update_all_views(self):
        """Slice data by lookback and push to the currently visible chart."""
        if self._yoy_df is None or self._yoy_df.empty:
            return

        sliced = self._slice_by_lookback(self._yoy_df)
        settings = self.settings_manager.get_all_settings()

        if self.stack.currentIndex() == 1:
            self.breakdown_view.update_data(sliced, settings)
        else:
            self.headline_view.update_data(sliced, settings)

    def _slice_by_lookback(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """Slice DataFrame to the current lookback period."""
        lb = self._current_lookback
        # Custom ISO date string (e.g. "2010-01-15")
        if "-" in lb:
            return df.loc[lb:]
        months = LOOKBACK_MONTHS.get(lb)
        if months is None:
            return df
        return df.tail(months)

    def _on_lookback_changed(self, lookback: str):
        """Handle lookback period change."""
        self._current_lookback = lookback
        self._update_all_views()

    # ========== Settings ==========

    def _on_settings_clicked(self):
        """Open settings dialog."""
        from PySide6.QtWidgets import QDialog
        from .widgets.cpi_settings_dialog import CpiSettingsDialog

        dialog = CpiSettingsDialog(
            self.theme_manager,
            current_settings=self.settings_manager.get_all_settings(),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if new_settings:
                self.settings_manager.update_settings(new_settings)
                self._apply_settings()
                # Re-render with new settings
                self._update_all_views()

    def _apply_settings(self):
        """Push current settings to views and toolbar."""
        show_breakdown = self.settings_manager.get_setting("show_breakdown")
        self.stack.setCurrentIndex(1 if show_breakdown else 0)

    def _apply_theme(self):
        """Apply theme to all child widgets."""
        super()._apply_theme()
        theme = self.theme_manager.current_theme
        self.headline_view.set_theme(theme)
        self.breakdown_view.set_theme(theme)
