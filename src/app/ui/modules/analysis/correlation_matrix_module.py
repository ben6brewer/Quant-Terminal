"""Correlation Matrix Module - Pearson correlation heatmap for selected tickers."""

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule

from .widgets.analysis_toolbar import AnalysisToolbar
from .widgets.ticker_list_panel import TickerListPanel
from .widgets.matrix_heatmap import MatrixHeatmap
from .widgets.analysis_settings_dialog import AnalysisSettingsDialog


class CorrelationMatrixModule(BaseModule):
    """Correlation Matrix module - lower-triangle heatmap of Pearson correlations."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)
        self._last_matrix = None
        self._last_metadata = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.controls = AnalysisToolbar(
            self.theme_manager,
            show_simulations=False,
            show_periodicity=True,
            run_label="Run",
        )
        layout.addWidget(self.controls)

        # Ticker list | heatmap
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.ticker_panel = TickerListPanel(self.theme_manager, include_portfolios=True)
        body.addWidget(self.ticker_panel, stretch=0)

        self.heatmap = MatrixHeatmap()
        self.heatmap.show_placeholder("Click 'Run' to compute correlation matrix")
        body.addWidget(self.heatmap, stretch=1)

        layout.addLayout(body, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.lookback_changed.connect(self._on_lookback_changed)
        self.controls.periodicity_changed.connect(self._on_periodicity_changed)
        self.controls.run_clicked.connect(self._run)
        self.controls.settings_clicked.connect(self._on_settings_clicked)
        self.controls.info_clicked.connect(self._on_info_clicked)
        self.ticker_panel.tickers_changed.connect(self._on_tickers_changed)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def _load_settings(self):
        lookback = self.settings_manager.get_lookback_days()
        self.controls.set_lookback(lookback)
        self.controls.set_periodicity(self.settings_manager.get_periodicity())

    def _on_tickers_changed(self, tickers: list):
        self.settings_manager.set_tickers(tickers)

    def _on_lookback_changed(self, days: int):
        if days == -1:
            return  # Custom range: don't persist
        self.settings_manager.update_settings(
            {"lookback_days": days if days > 0 else None}
        )

    def _on_periodicity_changed(self, value: str):
        self.settings_manager.set_periodicity(value)

    def create_settings_manager(self):
        from .services.analysis_settings_manager import AnalysisSettingsManager
        return AnalysisSettingsManager()

    def create_settings_dialog(self, current_settings):
        return AnalysisSettingsDialog(
            self.theme_manager, current_settings, mode="correlation", parent=self
        )

    def _on_settings_changed(self, new_settings):
        if self._last_matrix is not None:
            decimals = new_settings.get("corr_decimals", 3)
            colorscale = new_settings.get("matrix_colorscale", "Green-Yellow-Red")
            self.heatmap.begin_update()
            self.heatmap.set_theme(self.theme_manager.current_theme)
            show_overlay = new_settings.get("show_matrix_overlay", True)
            self.heatmap.set_data(self._last_matrix, f".{decimals}f", colorscale,
                                 absolute_colors=new_settings.get("corr_fixed_color_scale", True),
                                 metadata=self._last_metadata if show_overlay else None)
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
            FrontierCalculationService.calculate_correlation_matrix,
            tickers, lookback,
            start_date=start_date, end_date=end_date,
            periodicity=self.controls.get_periodicity(),
            loading_message="Computing correlation matrix...",
            on_complete=self._on_complete,
            on_error=self._on_error,
        )

    def _on_complete(self, result):
        corr_matrix = result["matrix"]
        self._last_matrix = corr_matrix
        self._last_metadata = result
        decimals = self.settings_manager.get_corr_decimals()
        colorscale = self.settings_manager.get_matrix_colorscale()
        self.heatmap.begin_update()
        self.heatmap.set_theme(self.theme_manager.current_theme)
        fixed = self.settings_manager.get_corr_fixed_color_scale()
        show_overlay = self.settings_manager.get_show_matrix_overlay()
        self.heatmap.set_data(corr_matrix, f".{decimals}f", colorscale, absolute_colors=fixed,
                             metadata=result if show_overlay else None)
        self.heatmap.end_update()
        self.heatmap.flush_and_repaint()

    def _on_error(self, error_msg: str):
        self.heatmap.show_placeholder(f"Error: {error_msg}")

    def _apply_theme(self):
        self.setStyleSheet(f"background-color: {self._get_theme_bg()};")
        self.heatmap.set_theme(self.theme_manager.current_theme)
