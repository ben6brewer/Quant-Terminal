"""Efficient Frontier Module - Monte Carlo simulation and portfolio optimization."""

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Signal, QThread, QObject

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.ui.modules.base_module import BaseModule

from .services.analysis_settings_manager import AnalysisSettingsManager
from .widgets.analysis_controls import AnalysisControls
from .widgets.ticker_list_panel import TickerListPanel
from .widgets.frontier_chart import FrontierChart
from .widgets.weights_panel import WeightsPanel
from .widgets.ef_settings_dialog import EFSettingsDialog


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


class EfficientFrontierModule(BaseModule):
    """Efficient Frontier module with Monte Carlo scatter, frontier curve,
    tangency/min-vol/sortino portfolios, CML, and weights table.
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        self.settings_manager = AnalysisSettingsManager()
        self._last_results: Optional[dict] = None
        self._current_gamma = 0.0

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
            show_risk_aversion=True,
            run_label="Run",
        )
        layout.addWidget(self.controls)

        # Content: ticker list | chart | weights
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        self.ticker_panel = TickerListPanel(self.theme_manager)
        content.addWidget(self.ticker_panel)

        self.chart = FrontierChart()
        self.chart.show_placeholder()
        content.addWidget(self.chart, stretch=1)

        self.weights_panel = WeightsPanel(self.theme_manager)
        content.addWidget(self.weights_panel)

        layout.addLayout(content, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_loaded.connect(self._on_portfolio_loaded)
        self.controls.lookback_changed.connect(self._on_lookback_changed)
        self.controls.simulations_changed.connect(self._on_simulations_changed)
        self.controls.risk_aversion_changed.connect(self._on_risk_aversion_changed)
        self.controls.run_clicked.connect(self._run)
        self.controls.settings_clicked.connect(self._on_settings_clicked)
        self.ticker_panel.tickers_changed.connect(self._on_tickers_changed)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def _load_settings(self):
        lookback = self.settings_manager.get_lookback_days()
        self.controls.set_lookback(lookback)

        sims = self.settings_manager.get_num_simulations()
        self.controls.set_simulations(sims)

        # Apply EF chart settings
        self.chart.apply_settings(self.settings_manager.get_all_settings())

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

    def _on_risk_aversion_changed(self, gamma: float):
        self._current_gamma = gamma
        if gamma > 0 and self._last_results is not None:
            self._compute_and_plot_indifference(gamma)
        else:
            self.chart.clear_indifference_curve()
            self.weights_panel.clear_optimal_results()

    def _on_settings_clicked(self):
        from PySide6.QtWidgets import QDialog
        dialog = EFSettingsDialog(
            self.theme_manager,
            current_settings=self.settings_manager.get_all_settings(),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if new_settings:
                self.settings_manager.update_settings(new_settings)
                all_settings = self.settings_manager.get_all_settings()
                self.chart.apply_settings(all_settings)
                if self._last_results is not None:
                    self.chart.plot_results(self._last_results)
                    self.weights_panel.set_results(self._last_results, all_settings)
                    # Re-apply or clear indifference curve based on new settings
                    if self._current_gamma > 0 and all_settings.get("ef_show_indifference_curve", True):
                        self._compute_and_plot_indifference(self._current_gamma)
                    else:
                        self.chart.clear_indifference_curve()
                        self.weights_panel.clear_optimal_results()
                self.chart.set_theme(self.theme_manager.current_theme)

    def _compute_and_plot_indifference(self, gamma: float):
        """Calculate and plot the indifference curve for the given risk aversion."""
        results = self._last_results
        if results is None:
            return

        all_settings = self.settings_manager.get_all_settings()
        if not all_settings.get("ef_show_indifference_curve", True):
            return

        from .services.frontier_calculation_service import FrontierCalculationService
        optimal = FrontierCalculationService.calculate_optimal_portfolio(
            gamma, results["cov_matrix"], results["mean_returns"]
        )

        # Determine max chart vol for curve extent
        max_chart_vol = max(results.get("frontier_vols", [0.5]) or [0.5])

        self.chart.plot_indifference_curve(
            gamma,
            optimal["optimal_vol"],
            optimal["optimal_ret"],
            optimal["utility"],
            max_chart_vol,
        )

        self.weights_panel.set_optimal_results(
            results["tickers"],
            optimal["optimal_weights"],
            optimal["utility"],
            gamma,
        )

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
        self._last_results = results
        self.chart.plot_results(results)
        self.chart.set_theme(self.theme_manager.current_theme)
        all_settings = self.settings_manager.get_all_settings()
        self.weights_panel.set_results(results, all_settings)
        # Read gamma directly from input to avoid signal-timing issues
        gamma = self.controls.get_risk_aversion()
        self._current_gamma = gamma
        if gamma > 0 and all_settings.get("ef_show_indifference_curve", True):
            self._compute_and_plot_indifference(gamma)
        self._hide_loading()
        self._cleanup_worker()

    def _on_error(self, error_msg: str):
        self.chart.show_placeholder(f"Error: {error_msg}")
        self._hide_loading()
        self._cleanup_worker()

    def _apply_theme(self):
        self.setStyleSheet(f"background-color: {self._get_theme_bg()};")
        self.chart.set_theme(self.theme_manager.current_theme)
