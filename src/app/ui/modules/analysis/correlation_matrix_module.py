"""Correlation Matrix Module - Pearson correlation heatmap for selected tickers."""

from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Signal, QThread, QObject

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.ui.widgets.common.loading_overlay import LoadingOverlay
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

from .services.analysis_settings_manager import AnalysisSettingsManager
from .widgets.analysis_controls import AnalysisControls
from .widgets.ticker_list_panel import TickerListPanel
from .widgets.matrix_heatmap import MatrixHeatmap
from .widgets.analysis_settings_dialog import AnalysisSettingsDialog


class _CorrWorker(QObject):
    """Background worker for correlation matrix calculation."""

    finished = Signal(object)  # pd.DataFrame
    error = Signal(str)

    def __init__(self, tickers, lookback_days, start_date=None, end_date=None):
        super().__init__()
        self._tickers = tickers
        self._lookback_days = lookback_days
        self._start_date = start_date
        self._end_date = end_date

    def run(self):
        try:
            from .services.frontier_calculation_service import FrontierCalculationService
            result = FrontierCalculationService.calculate_correlation_matrix(
                self._tickers, self._lookback_days,
                start_date=self._start_date, end_date=self._end_date,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class CorrelationMatrixModule(LazyThemeMixin, QWidget):
    """Correlation Matrix module - lower-triangle heatmap of Pearson correlations."""

    home_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        self.settings_manager = AnalysisSettingsManager()
        self._loading_overlay: Optional[LoadingOverlay] = None
        self._worker: Optional[_CorrWorker] = None
        self._thread: Optional[QThread] = None
        self._last_matrix = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.controls = AnalysisControls(
            self.theme_manager,
            show_simulations=False,
            run_label="Run",
        )
        layout.addWidget(self.controls)

        # Ticker list | heatmap
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.ticker_panel = TickerListPanel(self.theme_manager)
        body.addWidget(self.ticker_panel, stretch=0)

        self.heatmap = MatrixHeatmap()
        self.heatmap.show_placeholder("Click 'Run' to compute correlation matrix")
        body.addWidget(self.heatmap, stretch=1)

        layout.addLayout(body, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_loaded.connect(self._on_portfolio_loaded)
        self.controls.lookback_changed.connect(self._on_lookback_changed)
        self.controls.run_clicked.connect(self._run)
        self.controls.settings_clicked.connect(self._show_settings_dialog)
        self.ticker_panel.tickers_changed.connect(self._on_tickers_changed)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def hideEvent(self, event):
        self._cancel_worker()
        super().hideEvent(event)

    def _load_settings(self):
        lookback = self.settings_manager.get_lookback_days()
        self.controls.set_lookback(lookback)

        portfolios = PortfolioDataService.list_portfolios_by_recent()
        self.controls.set_portfolio_list(portfolios)

    def _on_portfolio_loaded(self, tickers: list):
        self.ticker_panel.set_tickers(tickers)
        self.settings_manager.set_tickers(tickers)

    def _on_tickers_changed(self, tickers: list):
        self.settings_manager.set_tickers(tickers)

    def _on_lookback_changed(self, days: int):
        if days == -1:
            return  # Custom range: don't persist
        self.settings_manager.update_settings(
            {"lookback_days": days if days > 0 else None}
        )

    def _show_settings_dialog(self):
        current = {
            "corr_decimals": self.settings_manager.get_corr_decimals(),
            "matrix_colorscale": self.settings_manager.get_matrix_colorscale(),
        }
        dialog = AnalysisSettingsDialog(
            self.theme_manager, current, mode="correlation", parent=self
        )
        if dialog.exec() and dialog.get_settings():
            settings = dialog.get_settings()
            self.settings_manager.update_settings(settings)
            if self._last_matrix is not None:
                decimals = settings.get("corr_decimals", 3)
                colorscale = settings.get("matrix_colorscale", "Green-Yellow-Red")
                self.heatmap.begin_update()
                self.heatmap.set_theme(self.theme_manager.current_theme)
                self.heatmap.set_data(self._last_matrix, f".{decimals}f", colorscale)
                self.heatmap.end_update()
                self.heatmap.flush_and_repaint()

    def _run(self):
        tickers = self.ticker_panel.get_tickers()
        if len(tickers) < 2:
            self.heatmap.show_placeholder("Add at least 2 tickers to run")
            return

        self._cancel_worker()
        self._show_loading("Computing correlation matrix...")

        custom_range = self.controls.custom_date_range
        if custom_range:
            lookback = None
            start_date, end_date = custom_range
        else:
            lookback = self.settings_manager.get_lookback_days()
            start_date, end_date = None, None

        self._thread = QThread()
        self._worker = _CorrWorker(tickers, lookback, start_date, end_date)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_complete)
        self._worker.error.connect(self._on_error)

        self._thread.start()

    def _on_complete(self, corr_matrix):
        self._last_matrix = corr_matrix
        decimals = self.settings_manager.get_corr_decimals()
        colorscale = self.settings_manager.get_matrix_colorscale()
        self.heatmap.begin_update()
        self.heatmap.set_theme(self.theme_manager.current_theme)
        self.heatmap.set_data(corr_matrix, f".{decimals}f", colorscale)
        self._hide_loading()
        self.heatmap.end_update()
        self.heatmap.flush_and_repaint()
        self._cleanup_worker()

    def _on_error(self, error_msg: str):
        self.heatmap.show_placeholder(f"Error: {error_msg}")
        self._hide_loading()
        self._cleanup_worker()

    def _cleanup_worker(self):
        """Safely stop thread and release references."""
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None

    def _cancel_worker(self):
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self._worker = None
        self._thread = None

    def _show_loading(self, message: str = "Loading..."):
        if self._loading_overlay is None:
            self._loading_overlay = LoadingOverlay(self, self.theme_manager, message)
        else:
            self._loading_overlay.set_message(message)
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    def _hide_loading(self):
        if self._loading_overlay:
            self._loading_overlay.hide()

    def _apply_theme(self):
        theme = self.theme_manager.current_theme
        if theme == "dark":
            bg = "#1e1e1e"
        elif theme == "light":
            bg = "#ffffff"
        else:
            bg = "#0d1420"
        self.setStyleSheet(f"background-color: {bg};")
        self.heatmap.set_theme(theme)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._loading_overlay:
            self._loading_overlay.resize(self.size())
