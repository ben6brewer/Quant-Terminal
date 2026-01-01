"""Return Distribution Module - Histogram visualization of portfolio returns."""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.services.returns_data_service import ReturnsDataService

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

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        # Settings manager
        self.settings_manager = DistributionSettingsManager()

        # Current state
        self._current_portfolio: str = ""
        self._current_interval: str = "daily"
        self._current_start_date: str = ""
        self._current_end_date: str = ""

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
        self.controls.interval_changed.connect(self._on_interval_changed)
        self.controls.date_range_changed.connect(self._on_date_range_changed)
        self.controls.custom_date_range_requested.connect(self._show_date_range_dialog)
        self.controls.settings_clicked.connect(self._show_settings_dialog)

        # Theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _refresh_portfolio_list(self):
        """Refresh the portfolio dropdown."""
        portfolios = PortfolioDataService.list_portfolios_by_recent()
        self.controls.update_portfolio_list(portfolios, self._current_portfolio)

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio selection change."""
        if name == self._current_portfolio:
            return

        self._current_portfolio = name
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
            self.chart.show_placeholder("Select a portfolio to view return distribution")
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
            # Get time-varying portfolio returns
            returns = ReturnsDataService.get_time_varying_portfolio_returns(
                self._current_portfolio,
                start_date=start_date,
                end_date=end_date,
                include_cash=include_cash,
                interval=self._current_interval,
            )

            if returns.empty:
                self.chart.show_placeholder("No return data available for this portfolio")
                return

            # Get cash drag if not excluded
            cash_drag = None
            if include_cash:
                cash_drag = ReturnsDataService.calculate_cash_drag(
                    self._current_portfolio,
                    start_date=start_date,
                    end_date=end_date,
                )

            # Update chart with all visualization settings
            self.chart.set_returns(
                returns,
                cash_drag=cash_drag,
                show_cash_drag=include_cash,
                show_kde_curve=show_kde_curve,
                show_normal_distribution=show_normal_distribution,
                show_mean_median_lines=show_mean_median_lines,
                show_cdf_view=show_cdf_view,
            )

        except Exception as e:
            print(f"Error updating distribution: {e}")
            self.chart.show_placeholder(f"Error loading data: {str(e)}")

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
