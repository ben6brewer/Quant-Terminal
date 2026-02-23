"""Covariance Matrix Module - Annualized covariance heatmap for selected tickers."""

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.ui.modules.base_module import BaseModule

from .services.analysis_settings_manager import AnalysisSettingsManager
from .widgets.analysis_controls import AnalysisControls
from .widgets.ticker_list_panel import TickerListPanel
from .widgets.matrix_heatmap import MatrixHeatmap
from .widgets.analysis_settings_dialog import AnalysisSettingsDialog


class CovarianceMatrixModule(BaseModule):
    """Covariance Matrix module - lower-triangle heatmap of annualized covariances."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        self.settings_manager = AnalysisSettingsManager()
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
        self.heatmap.show_placeholder("Click 'Run' to compute covariance matrix")
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
            "cov_decimals": self.settings_manager.get_cov_decimals(),
            "matrix_colorscale": self.settings_manager.get_matrix_colorscale(),
        }
        dialog = AnalysisSettingsDialog(
            self.theme_manager, current, mode="covariance", parent=self
        )
        if dialog.exec() and dialog.get_settings():
            settings = dialog.get_settings()
            self.settings_manager.update_settings(settings)
            if self._last_matrix is not None:
                decimals = settings.get("cov_decimals", 4)
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

        custom_range = self.controls.custom_date_range
        if custom_range:
            lookback = None
            start_date, end_date = custom_range
        else:
            lookback = self.settings_manager.get_lookback_days()
            start_date, end_date = None, None

        from .services.frontier_calculation_service import FrontierCalculationService

        self._run_worker(
            FrontierCalculationService.calculate_covariance_matrix,
            tickers, lookback,
            start_date=start_date, end_date=end_date,
            loading_message="Computing covariance matrix...",
            on_complete=self._on_complete,
            on_error=self._on_error,
        )

    def _on_complete(self, cov_matrix):
        self._last_matrix = cov_matrix
        decimals = self.settings_manager.get_cov_decimals()
        colorscale = self.settings_manager.get_matrix_colorscale()
        self.heatmap.begin_update()
        self.heatmap.set_theme(self.theme_manager.current_theme)
        self.heatmap.set_data(cov_matrix, f".{decimals}f", colorscale)
        self._hide_loading()
        self.heatmap.end_update()
        self.heatmap.flush_and_repaint()
        self._cleanup_worker()

    def _on_error(self, error_msg: str):
        self.heatmap.show_placeholder(f"Error: {error_msg}")
        self._hide_loading()
        self._cleanup_worker()

    def _apply_theme(self):
        self.setStyleSheet(f"background-color: {self._get_theme_bg()};")
        self.heatmap.set_theme(self.theme_manager.current_theme)
