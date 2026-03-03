"""PPI Module - Producer Price Index visualization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict

from PySide6.QtWidgets import QVBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule
from app.ui.modules.inflation.services import InflationFredService
from .services.ppi_settings_manager import PpiSettingsManager
from .widgets.ppi_toolbar import PpiToolbar
from .widgets.ppi_chart import PpiChart

if TYPE_CHECKING:
    import pandas as pd

LOOKBACK_MONTHS = {
    "1Y": 12, "2Y": 24, "5Y": 60, "10Y": 120, "20Y": 240, "Max": None,
}


class PpiModule(BaseModule):
    """PPI module — 4 PPI series YoY% from FRED."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(theme_manager, parent)

        self.settings_manager = PpiSettingsManager()
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

        self.toolbar = PpiToolbar(self.theme_manager)
        layout.addWidget(self.toolbar)

        self.chart = PpiChart()
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
            self.chart.show_placeholder("FRED API key required.\nSet your key in Settings > API Keys.")

    def _fetch_data(self):
        self._run_worker(
            InflationFredService.fetch_all_data,
            loading_message="Fetching PPI data from FRED...",
            on_complete=self._on_data_fetched,
            on_error=self._on_fetch_error,
        )

    def _on_data_fetched(self, result):
        self._hide_loading()
        self._cleanup_worker()
        if result is None:
            self.chart.show_placeholder("Failed to fetch PPI data.")
            return
        self._data = result
        ppi_df = result.get("ppi")
        if ppi_df is not None and not ppi_df.empty and "PPI Final Demand" in ppi_df.columns:
            s = ppi_df["PPI Final Demand"].dropna()
            if not s.empty:
                self.toolbar.update_info(ppi_final=float(s.iloc[-1]))
        self._render()

    def _on_fetch_error(self, error_msg: str):
        self._hide_loading()
        self._cleanup_worker()
        self.chart.show_placeholder(f"Error fetching data: {error_msg}")

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
        ppi_df = self._slice_monthly(self._data.get("ppi"))
        self.chart.update_data(ppi_df, settings)

    def _on_lookback_changed(self, lookback: str):
        self._current_lookback = lookback
        self.settings_manager.update_settings({"lookback": lookback})
        self._render()

    def _on_settings_clicked(self):
        from PySide6.QtWidgets import QDialog, QCheckBox, QDialogButtonBox
        from app.ui.widgets.common.themed_dialog import ThemedDialog

        class PpiSettingsDialog(ThemedDialog):
            def __init__(self, theme_manager, current_settings, parent=None):
                self._current = current_settings
                self._checks = {}
                super().__init__(theme_manager, "PPI Settings", parent, min_width=340)

            def _setup_content(self, layout):
                options = [
                    ("show_gridlines", "Show gridlines"),
                    ("show_crosshair", "Show crosshair"),
                    ("show_legend", "Show legend"),
                    ("show_hover_tooltip", "Show hover tooltip"),
                    ("show_ppi_final_demand", "Show PPI Final Demand"),
                    ("show_ppi_core", "Show PPI Core"),
                    ("show_ppi_energy", "Show PPI Energy"),
                    ("show_ppi_services", "Show PPI Services"),
                ]
                for key, label in options:
                    cb = QCheckBox(label)
                    cb.setChecked(self._current.get(key, True))
                    self._checks[key] = cb
                    layout.addWidget(cb)
                bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                bb.accepted.connect(self.accept)
                bb.rejected.connect(self.reject)
                layout.addWidget(bb)

            def get_settings(self):
                return {k: cb.isChecked() for k, cb in self._checks.items()}

        dialog = PpiSettingsDialog(
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

    def _apply_theme(self):
        super()._apply_theme()
        self.chart.set_theme(self.theme_manager.current_theme)
