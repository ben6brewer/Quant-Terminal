"""Return Distribution Module - Histogram visualization of portfolio returns."""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.services.returns_data_service import ReturnsDataService
from app.ui.widgets.common.custom_message_box import CustomMessageBox

from .services.distribution_settings_manager import DistributionSettingsManager
from .widgets.distribution_controls import DistributionControls
from .widgets.distribution_chart import DistributionChart
from .widgets.distribution_settings_dialog import DistributionSettingsDialog
from .widgets.date_range_dialog import DateRangeDialog


class ReturnDistributionModule(QWidget):
    """
    Portfolio Return Distribution module.

    Displays a histogram of portfolio returns with statistical analysis.
    Supports time-varying weights based on transaction history.
    """

    # Signal emitted when user clicks home button
    home_clicked = Signal()

    # Window name to trading days mapping
    WINDOW_TO_DAYS = {
        "1 Month": 21,
        "3 Months": 63,
        "6 Months": 126,
        "1 Year": 252,
        "3 Years": 756,
        "5 Years": 1260,
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        # Settings manager
        self.settings_manager = DistributionSettingsManager()

        # Current state
        self._current_portfolio: str = ""  # Can be portfolio name or ticker
        self._is_ticker_mode: bool = False  # True if viewing a single ticker
        self._current_interval: str = "Daily"
        self._current_start_date: str = ""
        self._current_end_date: str = ""
        self._current_metric: str = "Returns"
        self._current_window: str = ""
        self._current_benchmark: str = ""
        self._portfolio_list: list = []  # Cache of available portfolios

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

        # Load portfolio list
        self._refresh_portfolio_list()

    def _setup_ui(self):
        """Setup the module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = DistributionControls(self.theme_manager)
        layout.addWidget(self.controls)

        # Distribution chart (histogram + stats)
        self.chart = DistributionChart(self.theme_manager)
        layout.addWidget(self.chart, stretch=1)

    def _connect_signals(self):
        """Connect signals to slots."""
        # Controls signals
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.metric_changed.connect(self._on_metric_changed)
        self.controls.window_changed.connect(self._on_window_changed)
        self.controls.interval_changed.connect(self._on_interval_changed)
        self.controls.date_range_changed.connect(self._on_date_range_changed)
        self.controls.custom_date_range_requested.connect(self._show_date_range_dialog)
        self.controls.settings_clicked.connect(self._show_settings_dialog)
        self.controls.benchmark_changed.connect(self._on_benchmark_changed)

        # Theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _refresh_portfolio_list(self):
        """Refresh the portfolio dropdown and benchmark dropdown."""
        self._portfolio_list = PortfolioDataService.list_portfolios_by_recent()
        self.controls.update_portfolio_list(self._portfolio_list, self._current_portfolio)
        self.controls.update_benchmark_list(self._portfolio_list)

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio/ticker selection change."""
        if name == self._current_portfolio:
            return

        self._current_portfolio = name
        # Check if this is a portfolio or a ticker
        self._is_ticker_mode = name not in self._portfolio_list
        self._update_distribution()

    def _on_metric_changed(self, metric: str):
        """Handle metric selection change."""
        if metric == self._current_metric:
            return

        self._current_metric = metric
        # Update chart labels before updating data
        self.chart.set_metric(metric)
        self._update_distribution()

    def _on_window_changed(self, window: str):
        """Handle window selection change for rolling metrics."""
        if window == self._current_window:
            return

        self._current_window = window
        self._update_distribution()

    def _on_interval_changed(self, interval: str):
        """Handle interval selection change."""
        if interval == self._current_interval:
            return

        self._current_interval = interval
        self._update_distribution()

    def _on_date_range_changed(self, start_date: str, end_date: str):
        """Handle date range change."""
        self._current_start_date = start_date
        self._current_end_date = end_date
        self._update_distribution()

    def _on_benchmark_changed(self, benchmark: str):
        """Handle benchmark selection change."""
        self._current_benchmark = benchmark
        self._update_distribution()

    def _show_date_range_dialog(self):
        """Show the custom date range dialog."""
        dialog = DateRangeDialog(self.theme_manager, self)
        if dialog.exec():
            start_date, end_date = dialog.get_date_range()
            if start_date and end_date:
                self.controls.set_custom_date_range(start_date, end_date)

    def _show_settings_dialog(self):
        """Show the settings dialog."""
        current_settings = self.settings_manager.get_all_settings()
        dialog = DistributionSettingsDialog(
            self.theme_manager, current_settings, self
        )
        if dialog.exec():
            new_settings = dialog.get_settings()
            if new_settings:
                self.settings_manager.update_settings(new_settings)
                self._update_distribution()

    def _update_distribution(self):
        """Update the distribution chart with current settings."""
        if not self._current_portfolio:
            self.chart.show_placeholder("Type a ticker or select a portfolio")
            return

        # Get settings
        exclude_cash = self.settings_manager.get_setting("exclude_cash")
        include_cash = not exclude_cash

        # Get visualization settings
        show_kde_curve = self.settings_manager.get_setting("show_kde_curve")
        show_normal_distribution = self.settings_manager.get_setting("show_normal_distribution")
        show_mean_median_lines = self.settings_manager.get_setting("show_mean_median_lines")
        show_cdf_view = self.settings_manager.get_setting("show_cdf_view")

        # Get date range
        start_date = self._current_start_date if self._current_start_date else None
        end_date = self._current_end_date if self._current_end_date else None

        try:
            # Get data based on selected metric and mode (ticker vs portfolio)
            data = self._get_metric_data(start_date, end_date, include_cash)

            if data is None or data.empty:
                if self._is_ticker_mode:
                    if self._current_metric != "Returns":
                        # Non-Returns metrics not supported for tickers
                        self.chart.show_placeholder(
                            f"'{self._current_metric}' is only available for portfolios.\n"
                            f"Select 'Returns' to view {self._current_portfolio} distribution."
                        )
                    else:
                        # Show error for invalid ticker and reset
                        CustomMessageBox.warning(
                            self.theme_manager,
                            self,
                            "Ticker Not Found",
                            f"Ticker '{self._current_portfolio}' not found. Please check the symbol and try again."
                        )
                        self._current_portfolio = ""
                        self.controls.portfolio_combo.setCurrentIndex(-1)
                        self.chart.show_placeholder("Type a ticker or select a portfolio")
                else:
                    self.chart.show_placeholder(f"No {self._current_metric.lower()} data available")
                return

            # Get cash drag if showing Returns with cash included (only for portfolios)
            cash_drag = None
            if self._current_metric == "Returns" and include_cash and not self._is_ticker_mode:
                cash_drag = ReturnsDataService.calculate_cash_drag(
                    self._current_portfolio,
                    start_date=start_date,
                    end_date=end_date,
                )

            # Get benchmark returns if specified (only for Returns metric)
            benchmark_returns = None
            benchmark_name = ""
            if self._current_benchmark and self._current_metric == "Returns":
                benchmark_returns, benchmark_name, error_msg = self._get_benchmark_data(
                    start_date, end_date, include_cash
                )
                # If benchmark couldn't be loaded, show error and reset to None
                if error_msg:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Benchmark Not Found",
                        error_msg
                    )
                    # Reset benchmark to None
                    self._current_benchmark = ""
                    self.controls.reset_benchmark()
                    benchmark_returns = None
                    benchmark_name = ""

            # Update chart with all visualization settings
            self.chart.set_returns(
                data,
                cash_drag=cash_drag,
                show_cash_drag=(self._current_metric == "Returns" and include_cash),
                show_kde_curve=show_kde_curve,
                show_normal_distribution=show_normal_distribution,
                show_mean_median_lines=show_mean_median_lines,
                show_cdf_view=show_cdf_view,
                benchmark_returns=benchmark_returns,
                benchmark_name=benchmark_name,
            )

        except Exception as e:
            print(f"Error updating distribution: {e}")
            import traceback
            traceback.print_exc()
            self.chart.show_placeholder(f"Error loading data: {str(e)}")

    def _get_metric_data(self, start_date, end_date, include_cash):
        """
        Get data for the selected metric.

        Args:
            start_date: Start date for data range
            end_date: End date for data range
            include_cash: Whether to include cash in calculations

        Returns:
            pd.Series of metric values
        """
        metric = self._current_metric

        # If in ticker mode, only Returns metric is supported
        if self._is_ticker_mode:
            if metric == "Returns":
                return ReturnsDataService.get_ticker_returns(
                    self._current_portfolio,
                    start_date=start_date,
                    end_date=end_date,
                    interval=self._current_interval,
                )
            else:
                # Other metrics not supported for single tickers
                return None

        # Portfolio mode - use portfolio-specific methods
        if metric == "Returns":
            return ReturnsDataService.get_time_varying_portfolio_returns(
                self._current_portfolio,
                start_date=start_date,
                end_date=end_date,
                include_cash=include_cash,
                interval=self._current_interval,
            )

        elif metric == "Volatility":
            return ReturnsDataService.get_portfolio_volatility(
                self._current_portfolio,
                start_date=start_date,
                end_date=end_date,
                include_cash=include_cash,
                interval=self._current_interval,
            )

        elif metric == "Rolling Volatility":
            window_days = self.WINDOW_TO_DAYS.get(self._current_window, 21)
            return ReturnsDataService.get_rolling_volatility(
                self._current_portfolio,
                window_days=window_days,
                start_date=start_date,
                end_date=end_date,
                include_cash=include_cash,
            )

        elif metric == "Drawdown":
            return ReturnsDataService.get_drawdowns(
                self._current_portfolio,
                start_date=start_date,
                end_date=end_date,
                include_cash=include_cash,
            )

        elif metric == "Rolling Return":
            window_days = self.WINDOW_TO_DAYS.get(self._current_window, 252)
            return ReturnsDataService.get_rolling_returns(
                self._current_portfolio,
                window_days=window_days,
                start_date=start_date,
                end_date=end_date,
                include_cash=include_cash,
            )

        elif metric == "Time Under Water":
            return ReturnsDataService.get_time_under_water(
                self._current_portfolio,
                start_date=start_date,
                end_date=end_date,
                include_cash=include_cash,
            )

        else:
            # Default to returns
            return ReturnsDataService.get_time_varying_portfolio_returns(
                self._current_portfolio,
                start_date=start_date,
                end_date=end_date,
                include_cash=include_cash,
                interval=self._current_interval,
            )

    def _get_benchmark_data(self, start_date, end_date, include_cash):
        """
        Get benchmark returns data.

        Args:
            start_date: Start date for data range
            end_date: End date for data range
            include_cash: Whether to include cash in portfolio benchmark calculations

        Returns:
            Tuple of (pd.Series of returns, benchmark name string, error message or None)
        """
        import pandas as pd

        benchmark = self._current_benchmark

        if benchmark.startswith("[Portfolio] "):
            # It's a portfolio - get portfolio returns
            portfolio_name = benchmark.replace("[Portfolio] ", "")
            try:
                returns = ReturnsDataService.get_time_varying_portfolio_returns(
                    portfolio_name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                    interval=self._current_interval,
                )
                if returns is None or returns.empty:
                    return pd.Series(dtype=float), "", f"Portfolio '{portfolio_name}' has no return data available."
                return returns, portfolio_name, None
            except Exception as e:
                print(f"Error loading benchmark portfolio {portfolio_name}: {e}")
                return pd.Series(dtype=float), "", f"Could not load portfolio '{portfolio_name}'."
        else:
            # It's a ticker - get ticker returns
            try:
                returns = ReturnsDataService.get_ticker_returns(
                    benchmark,
                    start_date=start_date,
                    end_date=end_date,
                    interval=self._current_interval,
                )
                if returns is None or returns.empty:
                    return pd.Series(dtype=float), "", f"Ticker '{benchmark}' not found. Please check the symbol and try again."
                return returns, benchmark, None
            except Exception as e:
                print(f"Error loading benchmark ticker {benchmark}: {e}")
                return pd.Series(dtype=float), "", f"Could not load ticker '{benchmark}'. Please check the symbol and try again."

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
        elif theme == "bloomberg":
            bg_color = "#000814"
        else:
            bg_color = "#1e1e1e"

        self.setStyleSheet(f"ReturnDistributionModule {{ background-color: {bg_color}; }}")

    def refresh(self):
        """Refresh the module (called when navigating back)."""
        self._refresh_portfolio_list()
        if self._current_portfolio:
            self._update_distribution()
