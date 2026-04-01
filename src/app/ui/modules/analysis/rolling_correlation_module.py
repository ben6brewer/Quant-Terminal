"""Rolling Correlation Module - Time-series rolling correlation between two tickers."""

from PySide6.QtWidgets import QVBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule

from .widgets.rolling_toolbar import RollingToolbar
from .widgets.rolling_chart import RollingChart


class RollingCorrelationModule(BaseModule):
    """Rolling Correlation module — line chart of rolling Pearson correlation."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.controls = RollingToolbar(self.theme_manager, mode="correlation")
        layout.addWidget(self.controls)

        self.chart = RollingChart(mode="correlation")
        layout.addWidget(self.chart, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.run_clicked.connect(self._run)
        self.controls.settings_clicked.connect(self._on_settings_clicked)
        self.controls.info_clicked.connect(self._on_info_clicked)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def _load_settings(self):
        t1 = self.settings_manager.get_ticker1()
        t2 = self.settings_manager.get_ticker2()
        if t1 or t2:
            self.controls.set_tickers(t1, t2)

        window = self.settings_manager.get_rolling_window()
        self.controls.set_rolling_window(window)

        lookback = self.settings_manager.get_lookback_days()
        self.controls.set_lookback(lookback)

    def _run(self):
        t1 = self.controls.get_ticker1()
        t2 = self.controls.get_ticker2()

        if not t1 or not t2:
            self.chart.show_placeholder("Enter two tickers to compute rolling correlation")
            return

        # Persist tickers
        self.settings_manager.update_settings({"ticker1": t1, "ticker2": t2})

        window = self.controls.get_rolling_window()
        self.settings_manager.update_settings({"rolling_window": window})

        custom_range = self.controls.custom_date_range
        if custom_range:
            lookback = None
            start_date, end_date = custom_range
        else:
            lookback = self.settings_manager.get_lookback_days()
            start_date, end_date = None, None

        from .services.rolling_calculation_service import RollingCalculationService

        self._run_worker(
            RollingCalculationService.compute_rolling_correlation,
            t1, t2, window,
            lookback_days=lookback,
            start_date=start_date, end_date=end_date,
            loading_message="Computing rolling correlation...",
            on_complete=self._on_complete,
            on_error=self._on_error,
        )

    def _on_complete(self, result):
        dates, values = result
        settings = self.settings_manager.get_all_settings()
        self.chart.plot_rolling_data(dates, values, settings)
        self.chart.set_theme(self.theme_manager.current_theme)

    def _on_error(self, error_msg: str):
        self.chart.show_placeholder(f"Error: {error_msg}")

    def create_settings_manager(self):
        from .services.rolling_settings_manager import RollingSettingsManager
        return RollingSettingsManager()

    def create_settings_dialog(self, current_settings):
        from .widgets.rolling_settings_dialog import RollingSettingsDialog
        return RollingSettingsDialog(
            self.theme_manager, current_settings=current_settings,
            mode="correlation", parent=self,
        )

    def _on_settings_changed(self, new_settings):
        if self.chart._values is not None:
            self.chart.plot_rolling_data(
                self.chart._dates, self.chart._values,
                self.settings_manager.get_all_settings(),
            )
            self.chart.set_theme(self.theme_manager.current_theme)

    def _apply_theme(self):
        self.setStyleSheet(f"background-color: {self._get_theme_bg()};")
        self.chart.set_theme(self.theme_manager.current_theme)
