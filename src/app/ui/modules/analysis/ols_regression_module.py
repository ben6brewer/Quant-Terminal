"""OLS Regression Module - Scatter plot with regression line and statistics panel."""

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule

from .widgets.ols_toolbar import OLSToolbar
from .widgets.ols_scatter_chart import OLSScatterChart
from .widgets.ols_stats_panel import OLSStatsPanel


class OLSRegressionModule(BaseModule):
    """OLS Regression module — scatter plot with regression line and statistics panel."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)
        self._last_result = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = OLSToolbar(self.theme_manager)
        layout.addWidget(self.controls)

        # Content area: chart (stretch) + stats panel (fixed width)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.chart = OLSScatterChart()
        content_layout.addWidget(self.chart, stretch=1)

        self.stats_panel = OLSStatsPanel(self.theme_manager)
        content_layout.addWidget(self.stats_panel)

        layout.addLayout(content_layout, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.run_clicked.connect(self._run)
        self.controls.settings_clicked.connect(self._on_settings_clicked)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def _load_settings(self):
        tx = self.settings_manager.get_ticker_x()
        ty = self.settings_manager.get_ticker_y()
        if tx or ty:
            self.controls.set_tickers(tx, ty)

        data_mode = self.settings_manager.get_data_mode()
        self.controls.set_data_mode(data_mode)

        frequency = self.settings_manager.get_frequency()
        self.controls.set_frequency(frequency)

        lookback = self.settings_manager.get_lookback_days()
        self.controls.set_lookback(lookback)

        # Apply chart settings
        settings = self.settings_manager.get_all_settings()
        self.chart.apply_settings(settings)
        self.stats_panel.setVisible(settings.get("show_stats_panel", True))

    def _run(self):
        tx = self.controls.get_ticker_x()
        ty = self.controls.get_ticker_y()

        if not tx or not ty:
            self.chart.show_placeholder("Enter two tickers to run regression")
            return

        # Persist tickers, data mode, and frequency
        data_mode = self.controls.get_data_mode()
        frequency = self.controls.get_frequency()
        self.settings_manager.update_settings({
            "ticker_x": tx,
            "ticker_y": ty,
            "data_mode": data_mode,
            "frequency": frequency,
        })

        custom_range = self.controls.custom_date_range
        if custom_range:
            lookback = None
            start_date, end_date = custom_range
        else:
            lookback = self.settings_manager.get_lookback_days()
            start_date, end_date = None, None

        from .services.ols_regression_service import OLSRegressionService

        self._run_worker(
            OLSRegressionService.compute_regression,
            tx, ty, data_mode,
            frequency=frequency,
            lookback_days=lookback,
            start_date=start_date, end_date=end_date,
            loading_message="Computing OLS regression...",
            on_complete=self._on_complete,
            on_error=self._on_error,
        )

    def _on_complete(self, result):
        self._last_result = result
        settings = self.settings_manager.get_all_settings()
        self.chart.apply_settings(settings)
        self.chart.plot_results(result)
        self.chart.set_theme(self.theme_manager.current_theme)
        self.stats_panel.update_stats(result)
        self.stats_panel.setVisible(settings.get("show_stats_panel", True))

    def _on_error(self, error_msg: str):
        self.chart.show_placeholder(f"Error: {error_msg}")
        self.stats_panel.show_placeholder(error_msg)

    def create_settings_manager(self):
        from .services.ols_settings_manager import OLSSettingsManager
        return OLSSettingsManager()

    def create_settings_dialog(self, current_settings):
        from .widgets.ols_settings_dialog import OLSSettingsDialog
        return OLSSettingsDialog(
            self.theme_manager, current_settings=current_settings, parent=self,
        )

    def _on_settings_changed(self, new_settings):
        settings = self.settings_manager.get_all_settings()
        self.chart.apply_settings(settings)
        self.stats_panel.setVisible(settings.get("show_stats_panel", True))
        if self._last_result is not None:
            self.chart.plot_results(self._last_result)
            self.chart.set_theme(self.theme_manager.current_theme)

    def _apply_theme(self):
        self.setStyleSheet(f"background-color: {self._get_theme_bg()};")
        self.chart.set_theme(self.theme_manager.current_theme)
