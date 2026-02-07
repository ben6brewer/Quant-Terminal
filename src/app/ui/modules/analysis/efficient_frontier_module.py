"""Efficient Frontier Module - Monte Carlo simulation and portfolio optimization."""

from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PySide6.QtCore import Signal, Qt, QThread, QObject

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.ui.widgets.common.loading_overlay import LoadingOverlay
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

from .services.analysis_settings_manager import AnalysisSettingsManager
from .widgets.analysis_controls import AnalysisControls
from .widgets.ticker_list_panel import TickerListPanel
from .widgets.frontier_chart import FrontierChart
from .widgets.weights_panel import WeightsPanel


class _EFWorker(QObject):
    """Background worker for efficient frontier calculation."""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, tickers, num_simulations, lookback_days,
                 start_date=None, end_date=None):
        super().__init__()
        self._tickers = tickers
        self._num_simulations = num_simulations
        self._lookback_days = lookback_days
        self._start_date = start_date
        self._end_date = end_date

    def run(self):
        try:
            from .services.frontier_calculation_service import FrontierCalculationService
            results = FrontierCalculationService.calculate_efficient_frontier(
                self._tickers, self._num_simulations, self._lookback_days,
                start_date=self._start_date, end_date=self._end_date,
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class EfficientFrontierModule(LazyThemeMixin, QWidget):
    """Efficient Frontier module with Monte Carlo scatter, frontier curve,
    tangency/min-vol/sortino portfolios, CML, and weights table.
    """

    home_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        self.settings_manager = AnalysisSettingsManager()
        self._loading_overlay: Optional[LoadingOverlay] = None
        self._worker: Optional[_EFWorker] = None
        self._thread: Optional[QThread] = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = AnalysisControls(
            self.theme_manager,
            show_simulations=True,
            run_label="Run EF",
        )
        layout.addWidget(self.controls)

        # Splitter: ticker list | chart | weights
        self.splitter = QSplitter(Qt.Horizontal)

        self.ticker_panel = TickerListPanel(self.theme_manager)
        self.splitter.addWidget(self.ticker_panel)

        self.chart = FrontierChart()
        self.chart.show_placeholder()
        self.splitter.addWidget(self.chart)

        self.weights_panel = WeightsPanel(self.theme_manager)
        self.splitter.addWidget(self.weights_panel)

        # Set stretch factors: ticker=0, chart=1, weights=0
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)

        layout.addWidget(self.splitter, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_loaded.connect(self._on_portfolio_loaded)
        self.controls.lookback_changed.connect(self._on_lookback_changed)
        self.controls.simulations_changed.connect(self._on_simulations_changed)
        self.controls.run_clicked.connect(self._run)
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

        sims = self.settings_manager.get_num_simulations()
        self.controls.set_simulations(sims)

        # Populate portfolio dropdown
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

    def _on_simulations_changed(self, count: int):
        self.settings_manager.update_settings({"num_simulations": count})

    def _run(self):
        tickers = self.ticker_panel.get_tickers()
        if len(tickers) < 2:
            self.chart.show_placeholder("Add at least 2 tickers to run")
            return

        self._cancel_worker()
        self._show_loading("Calculating efficient frontier...")

        sims = self.settings_manager.get_num_simulations()

        custom_range = self.controls.custom_date_range
        if custom_range:
            lookback = None
            start_date, end_date = custom_range
        else:
            lookback = self.settings_manager.get_lookback_days()
            start_date, end_date = None, None

        self._thread = QThread()
        self._worker = _EFWorker(tickers, sims, lookback, start_date, end_date)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_complete)
        self._worker.error.connect(self._on_error)

        self._thread.start()

    def _on_complete(self, results: dict):
        self.chart.plot_results(results)
        self.chart.set_theme(self.theme_manager.current_theme)
        self.weights_panel.set_results(results)
        self._hide_loading()
        self._cleanup_worker()

    def _on_error(self, error_msg: str):
        self.chart.show_placeholder(f"Error: {error_msg}")
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
        self.chart.set_theme(theme)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._loading_overlay:
            self._loading_overlay.resize(self.size())
