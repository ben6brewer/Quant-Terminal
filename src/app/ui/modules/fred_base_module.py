"""FRED Data Module Base — Shared lifecycle for all FRED chart modules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict

from PySide6.QtWidgets import QVBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule

if TYPE_CHECKING:
    import pandas as pd


# Standard lookback maps — subclasses can use or override via get_lookback_map()
LOOKBACK_MONTHS = {
    "1Y": 12, "2Y": 24, "5Y": 60, "10Y": 120, "20Y": 240, "Max": None,
}
LOOKBACK_WEEKS = {
    "1Y": 52, "2Y": 104, "5Y": 260, "10Y": 520, "20Y": 1040, "Max": None,
}
LOOKBACK_QUARTERS = {
    "5Y": 20, "10Y": 40, "20Y": 80, "Max": None,
}
LOOKBACK_DAYS = {
    "1Y": 252, "2Y": 504, "5Y": 1260, "10Y": 2520, "20Y": 5040, "Max": None,
}


class FredDataModule(BaseModule):
    """
    Base class for all FRED/yfinance data modules.

    Handles the full module lifecycle: init, UI setup, signal wiring,
    lazy data loading on showEvent, API key check, background fetch,
    lookback slicing, settings dialog, and theme application.

    Subclasses MUST implement:
        create_toolbar()         — return toolbar widget instance
        create_chart()           — return chart widget instance
        get_data_service()       — return the callable (e.g. Service.fetch_all_data)
        get_loading_message()    — e.g. "Fetching PCE data from FRED..."
        extract_chart_data(result) — extract + slice data, return args tuple for chart.update_data()

    Settings are handled by BaseModule. Subclasses provide either:
        SETTINGS_FILENAME + DEFAULT_SETTINGS class attrs (auto GenericSettingsManager), or
        create_settings_manager()  — return custom manager instance

    Subclasses MAY override:
        update_toolbar_info(result)   — extract stat, call toolbar.update_info()
        get_settings_options()        — list of (key, label) for checkbox settings dialog
        get_settings_dialog_title()   — title for the checkbox dialog (default: "Settings")
        create_settings_dialog(settings) — for complex dialogs (overrides checkbox pattern)
        slice_data(df)                — default is tail(n) from lookback map
        get_lookback_map()            — default: LOOKBACK_MONTHS
        get_fail_message()            — placeholder on fetch failure
        _connect_extra_signals()      — for view_changed etc.
        _apply_extra_settings()       — for view_mode etc.

    Auto-wiring: Set VIEW_MODE and/or DATA_MODE class attributes to auto-connect
    toolbar signals and apply settings without overriding the 3 boilerplate methods.
    """

    VIEW_MODE = None   # e.g. "view_mode" — auto-wires toolbar.view_changed
    DATA_MODE = None   # e.g. "data_mode" — auto-wires toolbar.data_mode_changed
    REQUIRES_API_KEY = True  # False for yfinance-powered modules

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        self._data_initialized = False
        self._data: Optional[Dict] = None
        self._current_lookback = self.settings_manager.get_setting("lookback")

        self._setup_ui()
        self._connect_signals()
        self._apply_settings()
        self._apply_theme()

    # ── Abstract methods (MUST override) ──────────────────────────────────

    def create_toolbar(self):
        raise NotImplementedError

    def create_chart(self):
        raise NotImplementedError

    def get_data_service(self):
        """Return the callable to invoke in background thread."""
        return self.get_fred_service()

    def get_fred_service(self):
        """Legacy hook — override get_data_service() instead for new modules."""
        raise NotImplementedError

    def get_loading_message(self) -> str:
        raise NotImplementedError

    def extract_chart_data(self, result: Dict) -> tuple:
        """Extract, slice, and return args tuple for chart.update_data().

        Example: return (self.slice_data(result.get("pce")),)
        """
        raise NotImplementedError

    # ── Optional overrides ────────────────────────────────────────────────

    def update_toolbar_info(self, result: Dict):
        """Update toolbar info labels from fetch result. Override per module."""
        pass

    def get_lookback_map(self) -> dict:
        return LOOKBACK_MONTHS

    def get_fail_message(self) -> str:
        return "Failed to fetch data."

    def _connect_extra_signals(self):
        """Connect additional signals. Auto-wires VIEW_MODE/DATA_MODE if set."""
        if self.VIEW_MODE and hasattr(self.toolbar, "view_changed"):
            self.toolbar.view_changed.connect(self._on_view_changed)
        if self.DATA_MODE and hasattr(self.toolbar, "data_mode_changed"):
            self.toolbar.data_mode_changed.connect(self._on_data_mode_changed)

    def _on_view_changed(self, view: str):
        self.settings_manager.update_settings({self.VIEW_MODE: view})
        self._render()

    def _on_data_mode_changed(self, mode: str):
        self.settings_manager.update_settings({self.DATA_MODE: mode})
        self._render()

    def _apply_extra_settings(self):
        """Apply additional settings. Auto-wires VIEW_MODE/DATA_MODE if set."""
        if self.VIEW_MODE and hasattr(self.toolbar, "set_active_view"):
            self.toolbar.set_active_view(
                self.settings_manager.get_setting(self.VIEW_MODE)
            )
        if self.DATA_MODE and hasattr(self.toolbar, "set_active_data_mode"):
            self.toolbar.set_active_data_mode(
                self.settings_manager.get_setting(self.DATA_MODE)
            )

    # ── UI Setup ──────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = self.create_toolbar()
        layout.addWidget(self.toolbar)

        self.chart = self.create_chart()
        layout.addWidget(self.chart, stretch=1)

    def _connect_signals(self):
        self.toolbar.home_clicked.connect(self.home_clicked.emit)
        if hasattr(self.toolbar, "lookback_changed"):
            self.toolbar.lookback_changed.connect(self._on_lookback_changed)
        self.toolbar.settings_clicked.connect(self._on_settings_clicked)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)
        self._connect_extra_signals()

    # ── Events ────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not self._data_initialized:
            self._data_initialized = True
            self._initialize_data()

    def hideEvent(self, event):
        super().hideEvent(event)

    # ── Data Loading ──────────────────────────────────────────────────────

    def _initialize_data(self):
        if self.REQUIRES_API_KEY:
            from app.services.fred_api_key_service import FredApiKeyService
            if not FredApiKeyService.has_api_key():
                self._show_api_key_dialog()
                return
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
            self.get_data_service(),
            loading_message=self.get_loading_message(),
            on_complete=self._on_data_fetched,
            on_error=self._on_fetch_error,
        )

    def _on_data_fetched(self, result):
        if result is None:
            self.chart.show_placeholder(self.get_fail_message())
            return
        self._data = result
        self.update_toolbar_info(result)
        self._render()

    def _on_fetch_error(self, error_msg: str):
        self.chart.show_placeholder(f"Error fetching data: {error_msg}")

    # ── Slicing & Rendering ───────────────────────────────────────────────

    def slice_data(self, df: "Optional[pd.DataFrame]") -> "Optional[pd.DataFrame]":
        """Slice a DataFrame to the current lookback period.

        Supports:
        - ISO date strings (contains '-') → df.loc[date:]
        - Lookback map entries → df.tail(n)
        - None/Max → return full df
        """
        if df is None or df.empty:
            return df
        lb = self._current_lookback
        # Custom ISO date string (e.g. "2020-01-15")
        if isinstance(lb, str) and "-" in lb:
            return df.loc[lb:]
        count = self.get_lookback_map().get(lb)
        if count is None:
            return df
        return df.tail(count)

    def _render(self):
        if self._data is None:
            return
        settings = self.settings_manager.get_all_settings()
        chart_args = self.extract_chart_data(self._data)
        self.chart.update_data(*chart_args, settings)

    # ── Lookback ──────────────────────────────────────────────────────────

    def _on_lookback_changed(self, lookback: str):
        self._current_lookback = lookback
        self.settings_manager.update_settings({"lookback": lookback})
        self._render()

    # ── Settings ──────────────────────────────────────────────────────────

    def _on_settings_changed(self, new_settings):
        self._apply_extra_settings()
        self._render()

    def _apply_settings(self):
        lookback = self.settings_manager.get_setting("lookback")
        if lookback is None:
            lookback = self.toolbar.lookback_combo.currentText()
        self._current_lookback = lookback
        self.toolbar.set_active_lookback(lookback)
        self._apply_extra_settings()

    # ── Theme ─────────────────────────────────────────────────────────────

    def _apply_theme(self):
        super()._apply_theme()
        self.chart.set_theme(self.theme_manager.current_theme)
