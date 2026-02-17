"""Rolling Covariance Module - Time-series rolling covariance between two tickers."""

from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtCore import Signal, QThread, QObject

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule

from .services.rolling_settings_manager import RollingSettingsManager
from .widgets.rolling_controls import RollingControls
from .widgets.rolling_chart import RollingChart


class _RollingCovWorker(QObject):
    """Background worker for rolling covariance calculation."""

    finished = Signal(object, object)  # (dates, values)
    error = Signal(str)

    def __init__(self, ticker1, ticker2, window, lookback_days,
                 start_date=None, end_date=None):
        super().__init__()
        self._ticker1 = ticker1
        self._ticker2 = ticker2
        self._window = window
        self._lookback_days = lookback_days
        self._start_date = start_date
        self._end_date = end_date

    def run(self):
        try:
            from .services.rolling_calculation_service import RollingCalculationService
            dates, values = RollingCalculationService.compute_rolling_covariance(
                self._ticker1, self._ticker2, self._window,
                lookback_days=self._lookback_days,
                start_date=self._start_date, end_date=self._end_date,
            )
            self.finished.emit(dates, values)
        except Exception as e:
            self.error.emit(str(e))


class RollingCovarianceModule(BaseModule):
    """Rolling Covariance module — line chart of rolling annualized covariance."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        self.settings_manager = RollingSettingsManager()

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.controls = RollingControls(self.theme_manager, mode="covariance")
        layout.addWidget(self.controls)

        self.chart = RollingChart(mode="covariance")
        layout.addWidget(self.chart, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.run_clicked.connect(self._run)
        self.controls.settings_clicked.connect(self._show_settings)
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
            self.chart.show_placeholder("Enter two tickers to compute rolling covariance")
            return

        # Persist tickers
        self.settings_manager.update_settings({"ticker1": t1, "ticker2": t2})

        self._cancel_worker()
        self._show_loading("Computing rolling covariance...")

        window = self.controls.get_rolling_window()
        self.settings_manager.update_settings({"rolling_window": window})

        custom_range = self.controls.custom_date_range
        if custom_range:
            lookback = None
            start_date, end_date = custom_range
        else:
            lookback = self.settings_manager.get_lookback_days()
            start_date, end_date = None, None

        self._thread = QThread()
        self._worker = _RollingCovWorker(
            t1, t2, window, lookback, start_date, end_date
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_complete)
        self._worker.error.connect(self._on_error)

        self._thread.start()

    def _on_complete(self, dates, values):
        settings = self.settings_manager.get_all_settings()
        self.chart.plot_rolling_data(dates, values, settings)
        self.chart.set_theme(self.theme_manager.current_theme)
        self._hide_loading()
        self._cleanup_worker()

    def _on_error(self, error_msg: str):
        self.chart.show_placeholder(f"Error: {error_msg}")
        self._hide_loading()
        self._cleanup_worker()

    def _show_settings(self):
        from PySide6.QtWidgets import QDialog
        from .widgets.rolling_settings_dialog import RollingSettingsDialog

        dialog = RollingSettingsDialog(
            self.theme_manager,
            current_settings=self.settings_manager.get_all_settings(),
            mode="covariance",
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if new_settings:
                self.settings_manager.update_settings(new_settings)
                # Re-render if data exists
                if self.chart._values is not None:
                    self.chart.plot_rolling_data(
                        self.chart._dates, self.chart._values,
                        self.settings_manager.get_all_settings(),
                    )
                    self.chart.set_theme(self.theme_manager.current_theme)

    def _apply_theme(self):
        self.setStyleSheet(f"background-color: {self._get_theme_bg()};")
        self.chart.set_theme(self.theme_manager.current_theme)
