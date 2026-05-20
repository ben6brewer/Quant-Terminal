"""Market Concentration Module — Rolling concentration metrics for the S&P 500."""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QTimer

from app.core.theme_manager import ThemeManager
from app.ui.modules.yfinance_base_module import YFinanceDataModule
from app.ui.modules.fred_base_module import LOOKBACK_DAYS

from .services.market_concentration_service import MarketConcentrationService
from .widgets.market_concentration_chart import MarketConcentrationChart
from .widgets.market_concentration_toolbar import MarketConcentrationToolbar


class MarketConcentrationModule(YFinanceDataModule):
    """Visualizes how concentrated the S&P 500 is in its largest constituents."""

    SETTINGS_FILENAME = "market_concentration_settings.json"
    DEFAULT_SETTINGS = {
        "metric": "Top N %",
        "top_n": 10,
        "lookback": "5Y",
        "show_gridlines": True,
        "show_crosshair": True,
        "show_hover_tooltip": True,
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._progress_timer: Optional[QTimer] = None
        super().__init__(theme_manager, parent)

    # ── UI factory methods ────────────────────────────────────────────────

    def create_toolbar(self):
        return MarketConcentrationToolbar(
            self.theme_manager,
            lookback_options=["1Y", "2Y", "5Y", "10Y", "20Y", "Max"],
            default_lookback_index=2,  # 5Y
        )

    def create_chart(self):
        return MarketConcentrationChart()

    def get_data_service(self):
        return MarketConcentrationService.fetch_all_data

    def get_loading_message(self) -> str:
        return "Computing market concentration history..."

    def get_fail_message(self) -> str:
        return "Failed to compute market concentration."

    def get_lookback_map(self) -> dict:
        return LOOKBACK_DAYS

    # ── Extra signals ─────────────────────────────────────────────────────

    def _connect_extra_signals(self):
        super()._connect_extra_signals()
        self.toolbar.metric_changed.connect(self._on_metric_changed)
        self.toolbar.top_n_changed.connect(self._on_top_n_changed)

    def _apply_extra_settings(self):
        super()._apply_extra_settings()
        metric = self.settings_manager.get_setting("metric") or "Top N %"
        self.toolbar.set_active_metric(metric)
        n = self.settings_manager.get_setting("top_n") or 10
        self.toolbar.set_top_n(n)

    def _on_metric_changed(self, metric: str):
        self.settings_manager.update_settings({"metric": metric})
        self._render()  # all data is in memory; no re-fetch

    def _on_top_n_changed(self, n: int):
        self.settings_manager.update_settings({"top_n": int(n)})
        self._render()

    # ── Settings dialog ───────────────────────────────────────────────────

    def get_settings_options(self):
        return [
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Market Concentration Settings"

    # ── Chart data extraction ─────────────────────────────────────────────

    def extract_chart_data(self, result: Dict) -> tuple:
        if not result:
            return (None, "Top N %", 10)

        metric = self.settings_manager.get_setting("metric") or "Top N %"
        try:
            n = int(self.settings_manager.get_setting("top_n") or 10)
        except (TypeError, ValueError):
            n = 10
        # Upper bound is the actual number of stored ranks (which is
        # min(MAX_N, ticker_count)). Falls back to ticker_count if no matrix.
        sorted_w = result.get("sorted_weights")
        max_n = sorted_w.shape[1] if sorted_w is not None else result.get("ticker_count", 10)
        n = max(1, min(max_n, n))

        if metric == "HHI":
            series = result.get("hhi")
        else:
            # "Top N %" (default)
            if sorted_w is None or sorted_w.empty:
                return (None, metric, n)
            series = sorted_w.iloc[:, :n].sum(axis=1) * 100.0

        if series is None or series.empty:
            return (None, metric, n)

        df = series.to_frame("value")
        sliced = self.slice_data(df)
        return (sliced, metric, n)

    # ── Progress polling (first fetch is slow) ────────────────────────────

    def _fetch_data(self):
        self._start_progress_polling()
        super()._fetch_data()

    def _start_progress_polling(self):
        if self._progress_timer is None:
            self._progress_timer = QTimer(self)
            self._progress_timer.timeout.connect(self._poll_progress)
        self._progress_timer.start(400)

    def _stop_progress_polling(self):
        if self._progress_timer is not None:
            self._progress_timer.stop()

    def _poll_progress(self):
        stage = MarketConcentrationService.progress_stage
        current = MarketConcentrationService.progress_current
        total = MarketConcentrationService.progress_total
        if self._loading_overlay and self._loading_overlay.isVisible():
            if total > 0 and current > 0:
                self._loading_overlay.set_progress(current, total, stage)
            elif stage:
                self._loading_overlay.set_message(stage)

    def _on_data_fetched(self, result):
        self._stop_progress_polling()
        # Tighten the spinbox cap to the actual constituent count.
        if result:
            sorted_w = result.get("sorted_weights")
            max_n = (
                sorted_w.shape[1]
                if sorted_w is not None
                else int(result.get("ticker_count", 1) or 1)
            )
            self.toolbar.set_max_n(max_n)
        super()._on_data_fetched(result)

    def _on_fetch_error(self, error_msg: str):
        self._stop_progress_polling()
        super()._on_fetch_error(error_msg)
