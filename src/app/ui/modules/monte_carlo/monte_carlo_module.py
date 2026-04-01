"""Monte Carlo Simulation Module - Portfolio projection and risk analysis."""

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtCore import Qt, Signal

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.services.returns_data_service import ReturnsDataService
from app.services.ticker_returns_service import TickerReturnsService
from app.ui.widgets.common import parse_portfolio_value
from app.ui.modules.base_module import BaseModule

from .services.monte_carlo_service import SimulationResult
from .services.simulation_worker import (
    SimulationWorker,
    SimulationParams,
    SimulationResultBundle,
)
from .widgets.monte_carlo_toolbar import MonteCarloToolbar
from .widgets.monte_carlo_chart import MonteCarloChart


class MonteCarloModule(BaseModule):
    """
    Monte Carlo Simulation module.

    Generates probability cones and risk metrics for portfolio projections
    using either historical bootstrap or parametric simulation methods.
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        # Current state
        self._current_portfolio: str = ""
        self._is_ticker_mode: bool = False
        self._current_method: str = "bootstrap"
        self._current_horizon: int = 252  # Trading days (1 year default)
        self._current_simulations: int = 1000
        self._current_benchmark: str = ""
        self._portfolio_list: list = []
        self._last_result: Optional[SimulationResult] = None

        # Background simulation worker
        self._simulation_worker: Optional[SimulationWorker] = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._refresh_portfolio_list()

        # Load saved settings
        self._load_settings()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_portfolio_list()

    def _setup_ui(self):
        """Setup the module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = MonteCarloToolbar(self.theme_manager)
        layout.addWidget(self.controls)

        # Chart
        self.chart = MonteCarloChart(self.theme_manager)
        layout.addWidget(self.chart, stretch=1)

    def _connect_signals(self):
        """Connect signals to slots."""
        # Controls signals
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.method_changed.connect(self._on_method_changed)
        self.controls.horizon_changed.connect(self._on_horizon_changed)
        self.controls.simulations_changed.connect(self._on_simulations_changed)
        self.controls.benchmark_changed.connect(self._on_benchmark_changed)
        self.controls.run_simulation.connect(self._run_simulation)
        self.controls.settings_clicked.connect(self._on_settings_clicked)
        self.controls.info_clicked.connect(self._on_info_clicked)

        # Theme changes (lazy - only apply when visible)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def hideEvent(self, event):
        """Handle hide event - cancel any running simulation."""
        self._cancel_running_simulation()
        super().hideEvent(event)

    def _load_settings(self):
        """Load saved settings."""
        settings = self.settings_manager.get_all_settings()
        self._current_method = settings.get("simulation_method", "bootstrap")
        saved_years = settings.get("n_years", 1)
        self._current_horizon = saved_years * 252  # Convert to trading days
        self._current_simulations = settings.get("n_simulations", 1000)

        # Update controls (set_horizon expects years)
        self.controls.set_method(self._current_method)
        self.controls.set_horizon(saved_years)
        self.controls.set_simulations(self._current_simulations)

    def _refresh_portfolio_list(self):
        """Refresh the portfolio dropdown."""
        self._portfolio_list = PortfolioDataService.list_portfolios_by_recent()
        current_port = self.controls.portfolio_combo.get_value()
        current_bench = self.controls.benchmark_combo.get_value()
        self.controls.set_portfolio_list(self._portfolio_list)
        self.controls.set_benchmark_list(self._portfolio_list)
        if current_port:
            self.controls.portfolio_combo.set_value(current_port)
        if current_bench:
            self.controls.benchmark_combo.set_value(current_bench)

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio/ticker selection change."""
        # Strip "[Port] " prefix if present
        name, is_portfolio = parse_portfolio_value(name)

        if name == self._current_portfolio:
            return

        if is_portfolio:
            self._is_ticker_mode = False
        else:
            self._is_ticker_mode = name not in self._portfolio_list

        self._current_portfolio = name

    def _on_method_changed(self, method: str):
        """Handle simulation method change."""
        self._current_method = method
        self.settings_manager.update_settings({"simulation_method": method})

    def _on_horizon_changed(self, trading_days: int):
        """Handle time horizon change (in trading days)."""
        self._current_horizon = trading_days
        # Store as years for settings (approximate)
        years = max(1, trading_days // 252)
        self.settings_manager.update_settings({"n_years": years})

    def _on_simulations_changed(self, count: int):
        """Handle simulation count change."""
        self._current_simulations = count
        self.settings_manager.update_settings({"n_simulations": count})

    def _on_benchmark_changed(self, benchmark: str):
        """Handle benchmark selection change."""
        benchmark, _ = parse_portfolio_value(benchmark)
        self._current_benchmark = benchmark

    def _cancel_running_simulation(self):
        """Cancel any in-progress simulation with non-blocking cleanup."""
        if self._simulation_worker is not None:
            try:
                self._simulation_worker.finished.disconnect(self._on_simulation_thread_done)
            except (RuntimeError, TypeError):
                pass
            self._simulation_worker.request_cancellation()

            from app.ui.modules.base_module import _global_orphaned_threads

            worker = self._simulation_worker
            _global_orphaned_threads.append(worker)

            def _on_done(w=worker):
                try:
                    _global_orphaned_threads.remove(w)
                except ValueError:
                    pass

            worker.finished.connect(_on_done, Qt.QueuedConnection)
            self._simulation_worker = None

    def _run_simulation(self):
        """Run Monte Carlo simulation in background thread."""
        if not self._current_portfolio:
            self.chart.show_placeholder("Select a portfolio or ticker first")
            return

        # Cancel any running simulation
        self._cancel_running_simulation()

        self._show_loading("Running simulation...")

        try:
            # Get historical returns for portfolio (quick operation on main thread)
            if self._is_ticker_mode:
                portfolio_returns = TickerReturnsService.get_ticker_returns(
                    self._current_portfolio, interval="daily"
                )
            else:
                portfolio_returns = ReturnsDataService.get_time_varying_portfolio_returns(
                    self._current_portfolio, include_cash=False, interval="daily"
                )

            if portfolio_returns.empty or len(portfolio_returns) < 30:
                self.chart.show_placeholder(
                    f"Insufficient data for {self._current_portfolio} "
                    "(need at least 30 trading days)"
                )
                self._hide_loading()
                return

            # Get benchmark returns if selected
            benchmark_returns = None
            if self._current_benchmark:
                try:
                    is_benchmark_ticker = self._current_benchmark not in self._portfolio_list
                    if is_benchmark_ticker:
                        benchmark_returns = TickerReturnsService.get_ticker_returns(
                            self._current_benchmark, interval="daily"
                        )
                    else:
                        benchmark_returns = ReturnsDataService.get_time_varying_portfolio_returns(
                            self._current_benchmark, include_cash=False, interval="daily"
                        )

                    if benchmark_returns.empty or len(benchmark_returns) < 30:
                        benchmark_returns = None
                except Exception:
                    benchmark_returns = None

            # Build simulation parameters
            params = SimulationParams(
                n_simulations=self._current_simulations,
                n_periods=self._current_horizon,
                initial_value=self.settings_manager.get_setting("initial_value"),
                block_size=self.settings_manager.get_setting("block_size"),
                method=self._current_method,
            )

            # Create and start background worker
            self._simulation_worker = SimulationWorker(
                portfolio_returns=portfolio_returns,
                params=params,
                benchmark_returns=benchmark_returns,
                parent=self,
            )
            self._simulation_worker.finished.connect(
                self._on_simulation_thread_done, Qt.QueuedConnection
            )
            self._simulation_worker.start()

        except Exception as e:
            self.chart.show_placeholder(f"Error: {str(e)}")
            self._hide_loading()

    def _on_simulation_thread_done(self):
        """Dispatch simulation result on main thread via QThread.finished."""
        worker = self._simulation_worker
        if worker is None:
            return
        if worker.error_msg is not None:
            self._on_simulation_error(worker.error_msg)
        else:
            self._on_simulation_complete(worker.result)

    def _on_simulation_complete(self, bundle: SimulationResultBundle):
        """Handle simulation completion (runs on main thread via signal)."""
        self._last_result = bundle.portfolio_result

        # Update chart with pre-computed statistics
        settings = self.settings_manager.get_all_settings()
        self.chart.set_simulation_result_with_stats(
            bundle,
            settings,
            portfolio_name=self._current_portfolio,
            benchmark_name=self._current_benchmark,
        )

        self._hide_loading()
        self._simulation_worker = None

    def _on_simulation_error(self, error_msg: str):
        """Handle simulation error."""
        self.chart.show_placeholder(f"Error: {error_msg}")
        self._hide_loading()
        self._simulation_worker = None

    def create_settings_manager(self):
        from .services.monte_carlo_settings_manager import MonteCarloSettingsManager
        return MonteCarloSettingsManager()

    def create_settings_dialog(self, current_settings):
        from .widgets.monte_carlo_settings_dialog import MonteCarloSettingsDialog
        return MonteCarloSettingsDialog(
            self.theme_manager, current_settings, parent=self,
            has_benchmark=bool(self._current_benchmark),
        )

    def _on_settings_changed(self, new_settings):
        self.chart.update_chart_settings(new_settings)
        if self._last_result is not None and self._current_portfolio:
            self._run_simulation()
