"""Asset Class Returns Module - Quilt chart of annual asset class performance."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QStackedWidget
from PySide6.QtCore import Qt, QThread, QTimer

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox
from app.ui.modules.base_module import BaseModule

from .services.asset_class_returns_service import AssetClassReturnsService
from .widgets.asset_class_returns_toolbar import AssetClassReturnsToolbar
from .widgets.asset_class_returns_table import AssetClassReturnsTable
from .widgets.asset_class_returns_tab_bar import AssetClassReturnsTabBar
from .widgets.asset_class_returns_settings_dialog import AssetClassReturnsSettingsDialog


class AssetClassReturnsModule(BaseModule):
    """Displays a quilt chart of annual returns ranked by asset class."""

    SETTINGS_FILENAME = "asset_class_returns_settings.json"
    DEFAULT_SETTINGS = {
        "decimals": 1,
        "label_mode": "label",
        "custom_tickers": [],
        "cagr_years": None,
        "show_cagr": True,
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        self._cached_data = None
        self._cached_custom_data = None

        # Separate worker for custom tab (BaseModule manages _worker/_thread for asset class)
        self._custom_worker = None
        self._custom_thread: Optional[QThread] = None

        # Debounce timer for custom ticker changes
        self._custom_debounce = QTimer(self)
        self._custom_debounce.setSingleShot(True)
        self._custom_debounce.setInterval(300)
        self._custom_debounce.timeout.connect(self._load_custom_data)

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = AssetClassReturnsToolbar(self.theme_manager)
        layout.addWidget(self.controls)

        # Tab bar
        self.tab_bar = AssetClassReturnsTabBar(self.theme_manager)
        layout.addWidget(self.tab_bar)

        # Stacked widget for tab content
        self.stack = QStackedWidget()

        # Tab 0: Asset Class Heatmap
        self.asset_class_container = QWidget()
        ac_layout = QHBoxLayout(self.asset_class_container)
        ac_layout.setContentsMargins(20, 10, 20, 10)
        self.table = AssetClassReturnsTable(self.theme_manager)
        ac_layout.addWidget(self.table)
        self.stack.addWidget(self.asset_class_container)

        # Tab 1: Custom Heatmap
        self.custom_container = QWidget()
        custom_layout = QHBoxLayout(self.custom_container)
        custom_layout.setContentsMargins(0, 10, 20, 10)
        custom_layout.setSpacing(0)

        from app.ui.modules.analysis.widgets.ticker_list_panel import TickerListPanel

        self.ticker_panel = TickerListPanel(self.theme_manager, include_portfolios=True)
        custom_layout.addWidget(self.ticker_panel)

        self.custom_table = AssetClassReturnsTable(self.theme_manager)
        custom_layout.addWidget(self.custom_table, stretch=1)

        self.stack.addWidget(self.custom_container)
        layout.addWidget(self.stack, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.settings_clicked.connect(self._on_settings_clicked)
        self.tab_bar.view_changed.connect(self._on_tab_changed)
        self.ticker_panel.tickers_changed.connect(self._on_tickers_changed)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    # ── Tab Switching ──────────────────────────────────────────────

    def _on_tab_changed(self, index: int):
        """Switch between asset class and custom heatmap tabs."""
        self.stack.setCurrentIndex(index)

        if index == 1:
            # Restore persisted tickers if panel is empty
            if not self.ticker_panel.get_tickers():
                saved = self.settings_manager.get_all_settings().get("custom_tickers", [])
                if saved:
                    self.ticker_panel.set_tickers(saved)
                    self._schedule_custom_reload()

    # ── Helpers ──────────────────────────────────────────────────────

    def _cagr_header_text(self):
        cagr_years = self.settings_manager.get_all_settings().get("cagr_years")
        if cagr_years is None:
            return "CAGR"
        s = f"{cagr_years:.2f}".rstrip("0").rstrip(".")
        return f"{s}yr CAGR"

    # ── Asset Class Data (uses BaseModule._run_worker) ─────────────

    def _load_data(self):
        cagr_years = self.settings_manager.get_all_settings().get("cagr_years")
        self.asset_class_container.hide()
        self._run_worker(
            AssetClassReturnsService.compute_annual_returns,
            cagr_years,
            loading_message="Loading asset class returns...",
            on_complete=self._on_data_complete,
            on_error=self._on_data_error,
        )

    def _on_data_complete(self, result):
        if not result or not result.get("years"):
            CustomMessageBox.information(
                self.theme_manager, self, "No Data",
                "No asset class return data available."
            )
        else:
            self._cached_data = result
            settings = self.settings_manager.get_all_settings()
            self.table.update_data(result, settings["decimals"], settings.get("label_mode", "label"), self._cagr_header_text(), settings.get("show_cagr", True))
            self.table.scroll_to_recent()
        self.asset_class_container.show()

    def _on_data_error(self, error_msg: str):
        self.asset_class_container.show()
        CustomMessageBox.critical(
            self.theme_manager, self, "Load Error", error_msg
        )

    # ── Custom Data (separate worker) ──────────────────────────────

    def _on_tickers_changed(self, tickers: list):
        """Handle ticker list changes — save and schedule reload."""
        self.settings_manager.update_settings({"custom_tickers": tickers})
        self._schedule_custom_reload()

    def _schedule_custom_reload(self):
        """Debounce custom data reloads."""
        self._custom_debounce.start()

    def _load_custom_data(self):
        """Load custom heatmap data in a background thread."""
        tickers = self.ticker_panel.get_tickers()
        if not tickers:
            self._cached_custom_data = None
            self.custom_table.update_data(
                {"years": [], "data": {}, "cagr": [], "asset_count": 0}, 1
            )
            return

        self._cancel_custom_worker()

        from app.services.calculation_worker import CalculationWorker

        cagr_years = self.settings_manager.get_all_settings().get("cagr_years")
        self._custom_thread = QThread()
        self._custom_worker = CalculationWorker(
            AssetClassReturnsService.compute_custom_returns, tickers, cagr_years
        )
        self._custom_worker.moveToThread(self._custom_thread)

        self._custom_thread.started.connect(self._custom_worker.run)
        self._custom_thread.finished.connect(self._on_custom_thread_done, Qt.QueuedConnection)

        self._custom_thread.start()

    def _on_custom_thread_done(self):
        """Dispatch custom worker result on main thread."""
        worker = self._custom_worker
        if worker is None:
            return
        if worker.error_msg is not None:
            self._on_custom_error(worker.error_msg)
        else:
            self._on_custom_complete(worker.result)

    def _on_custom_complete(self, result):
        self._cleanup_custom_worker()

        if result and result.get("years"):
            self._cached_custom_data = result
            settings = self.settings_manager.get_all_settings()
            self.custom_table.update_data(result, settings["decimals"], "ticker", self._cagr_header_text(), settings.get("show_cagr", True))
            self.custom_table.scroll_to_recent()
        else:
            self._cached_custom_data = None

    def _on_custom_error(self, error_msg: str):
        self._cleanup_custom_worker()

    def _cancel_custom_worker(self):
        """Cancel any running custom worker with proper Qt cleanup."""
        if self._custom_thread is not None:
            try:
                self._custom_thread.finished.disconnect(self._on_custom_thread_done)
            except (RuntimeError, TypeError):
                pass
        self._cleanup_custom_worker()

    def _cleanup_custom_worker(self):
        """Non-blocking cleanup: signal thread to quit, let it finish async."""
        if self._custom_thread is not None:
            thread = self._custom_thread
            worker = self._custom_worker
            thread.quit()

            from app.ui.modules.base_module import _global_orphaned_threads
            _global_orphaned_threads.append(thread)

            if worker is not None:
                _global_orphaned_threads.append(worker)

            def _on_done(t=thread, w=worker):
                try:
                    _global_orphaned_threads.remove(t)
                except ValueError:
                    pass
                if w is not None:
                    try:
                        _global_orphaned_threads.remove(w)
                    except ValueError:
                        pass

            thread.finished.connect(_on_done, Qt.QueuedConnection)
        self._custom_worker = None
        self._custom_thread = None

    # ── Settings ───────────────────────────────────────────────────

    def create_settings_dialog(self, current_settings):
        self._old_cagr_years = current_settings.get("cagr_years")
        return AssetClassReturnsSettingsDialog(self.theme_manager, current_settings, self)

    def _on_settings_changed(self, new_settings):
        new_cagr_years = new_settings.get("cagr_years")
        show_cagr = new_settings.get("show_cagr", True)
        if new_cagr_years != self._old_cagr_years:
            self._load_data()
            if self.ticker_panel.get_tickers():
                self._load_custom_data()
        else:
            cagr_header = self._cagr_header_text()
            if self._cached_data:
                self.table.re_render(new_settings["decimals"], new_settings.get("label_mode", "label"), cagr_header, show_cagr)
            if self._cached_custom_data:
                self.custom_table.re_render(new_settings["decimals"], "ticker", cagr_header, show_cagr)

    # ── Theme ──────────────────────────────────────────────────────

    def _apply_theme(self):
        bg = self._get_theme_bg()
        self.setStyleSheet(f"""
            AssetClassReturnsModule {{ background-color: {bg}; }}
            QWidget {{ background-color: {bg}; }}
        """)

    # ── Cleanup ────────────────────────────────────────────────────

    def hideEvent(self, event):
        self._cancel_custom_worker()
        self._custom_debounce.stop()
        super().hideEvent(event)
