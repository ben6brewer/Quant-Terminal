"""YFinance Data Module Base — Shared lifecycle for yfinance-powered chart modules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict

from PySide6.QtWidgets import QVBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule
from app.ui.modules.fred_base_module import (
    LOOKBACK_DAYS, LOOKBACK_WEEKS, LOOKBACK_MONTHS, LOOKBACK_QUARTERS,
)

if TYPE_CHECKING:
    import pandas as pd


class YFinanceDataModule(BaseModule):
    """
    Base class for yfinance-powered data modules.

    Same lifecycle as FredDataModule but without the FRED API key check.

    Subclasses MUST implement:
        create_toolbar()
        create_chart()
        get_data_service()       — return the callable (e.g. Service.fetch_all_data)
        get_loading_message()
        extract_chart_data(result)

    Subclasses MAY override:
        update_toolbar_info(result)
        get_settings_options()
        get_settings_dialog_title()
        create_settings_dialog(settings)
        slice_data(df)
        get_lookback_map()
        get_fail_message()
        _connect_extra_signals()
        _apply_extra_settings()
    """

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
        raise NotImplementedError

    def get_loading_message(self) -> str:
        raise NotImplementedError

    def extract_chart_data(self, result: Dict) -> tuple:
        raise NotImplementedError

    # ── Optional overrides ────────────────────────────────────────────────

    def update_toolbar_info(self, result: Dict):
        pass

    def get_lookback_map(self) -> dict:
        return LOOKBACK_DAYS

    def get_fail_message(self) -> str:
        return "Failed to fetch data."

    def _connect_extra_signals(self):
        pass

    def _apply_extra_settings(self):
        pass

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
        self._fetch_data()

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
        if df is None or df.empty:
            return df
        lb = self._current_lookback
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
