"""Fed Balance Sheet Module — Total assets line or breakdown stacked area."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict

from PySide6.QtWidgets import QVBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule
from app.ui.modules.monetary_policy.services import MonetaryFredService
from .services.fed_balance_sheet_settings_manager import FedBalanceSheetSettingsManager
from .widgets.fed_balance_sheet_toolbar import FedBalanceSheetToolbar
from .widgets.fed_balance_sheet_chart import FedBalanceSheetChart

if TYPE_CHECKING:
    import pandas as pd

LOOKBACK_WEEKS = {
    "1Y": 52, "2Y": 104, "5Y": 260, "10Y": 520, "20Y": 1040, "Max": None,
}


class FedBalanceSheetModule(BaseModule):
    """Fed Balance Sheet module — total assets or stacked area breakdown."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        self.settings_manager = FedBalanceSheetSettingsManager()
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

        self.toolbar = FedBalanceSheetToolbar(self.theme_manager)
        layout.addWidget(self.toolbar)

        self.chart = FedBalanceSheetChart()
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
            MonetaryFredService.fetch_all_data,
            loading_message="Fetching Fed balance sheet data from FRED...",
            on_complete=self._on_data_fetched,
            on_error=self._on_fetch_error,
        )

    def _on_data_fetched(self, result):
        self._hide_loading()
        self._cleanup_worker()
        if result is None:
            self.chart.show_placeholder("Failed to fetch Fed balance sheet data.")
            return
        self._data = result
        bs_df = result.get("balance_sheet")
        if bs_df is not None and not bs_df.empty and "Total Assets" in bs_df.columns:
            latest = bs_df["Total Assets"].dropna()
            if not latest.empty:
                self.toolbar.update_info(total_assets=float(latest.iloc[-1]))
        self._render()

    def _on_fetch_error(self, error_msg: str):
        self._hide_loading()
        self._cleanup_worker()
        self.chart.show_placeholder(f"Error fetching data: {error_msg}")

    def _slice_data(self, df: "Optional[pd.DataFrame]") -> "Optional[pd.DataFrame]":
        if df is None or df.empty:
            return df
        weeks = LOOKBACK_WEEKS.get(self._current_lookback)
        if weeks is None:
            return df
        return df.tail(weeks)

    def _render(self):
        if self._data is None:
            return
        settings = self.settings_manager.get_all_settings()
        bs_df = self._slice_data(self._data.get("balance_sheet"))
        usrec_df = self._data.get("usrec")
        self.chart.update_data(bs_df, usrec_df, settings)

    def _on_lookback_changed(self, lookback: str):
        self._current_lookback = lookback
        self.settings_manager.update_settings({"lookback": lookback})
        self._render()

    def _on_settings_clicked(self):
        from PySide6.QtWidgets import QDialog, QCheckBox, QDialogButtonBox

        from app.ui.widgets.common.themed_dialog import ThemedDialog

        class FedBSSettingsDialog(ThemedDialog):
            def __init__(self, theme_manager, current_settings, parent=None):
                self._current = current_settings
                self._checks = {}
                super().__init__(theme_manager, "Fed Balance Sheet Settings", parent, min_width=380)

            def _setup_content(self, layout):
                options = [
                    ("show_breakdown", "Show breakdown (Treasuries/MBS/Agency/Loans/Other)"),
                    ("show_treasuries", "Show Treasuries"),
                    ("show_mbs", "Show MBS"),
                    ("show_agency_debt", "Show Agency Debt"),
                    ("show_loans", "Show Loans"),
                    ("show_other", "Show Other"),
                    ("show_recession_bands", "Show recession shading"),
                    ("show_gridlines", "Show gridlines"),
                    ("show_crosshair", "Show crosshair"),
                    ("show_legend", "Show legend"),
                    ("show_hover_tooltip", "Show hover tooltip"),
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

        dialog = FedBSSettingsDialog(
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
