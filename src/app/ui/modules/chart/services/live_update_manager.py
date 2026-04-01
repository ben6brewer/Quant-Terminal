"""Live Update Manager - Manages live price polling for the chart module."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal

from app.services.calculation_worker import CalculationWorker
from app.services.live_bar_aggregator import LiveBarAggregator
from app.services.yahoo_finance_service import YahooFinanceService
from app.utils.market_hours import is_crypto_ticker, is_market_open_extended


class LiveUpdateManager(QObject):
    """
    Manages live price polling timers for stock and crypto tickers.

    Emits `bar_received` when new OHLCV data arrives from Yahoo Finance.
    The chart module connects this signal to update the chart UI.

    All signal emissions happen on the main thread via QThread.finished.
    """

    # Emitted when a new bar is fetched (ticker, today_bar DataFrame)
    bar_received = Signal(str, object)

    _POLL_INTERVAL_MS = 60_000  # 1 minute

    def __init__(
        self,
        get_ticker: Callable[[], str | None],
        get_interval: Callable[[], str],
        is_equation: Callable[[str], bool],
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._get_ticker = get_ticker
        self._get_interval = get_interval
        self._is_equation = is_equation

        self._live_aggregator = LiveBarAggregator()
        self._enabled = True
        self._fetch_in_progress = False
        self._fetch_thread: QThread | None = None
        self._fetch_worker: CalculationWorker | None = None
        self._fetch_ticker: str | None = None

        self._stock_poll_timer: QTimer | None = None
        self._crypto_poll_timer: QTimer | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        if not value:
            self.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, ticker: str) -> None:
        """Start live updates for a ticker."""
        if not self._enabled:
            return

        if self._is_equation(ticker):
            return

        if is_crypto_ticker(ticker):
            self._start_crypto_polling(ticker)
        else:
            if is_market_open_extended():
                self._start_stock_polling(ticker)

    def stop(self) -> None:
        """Stop all live updates (polling timers and any in-flight fetch)."""
        self._stop_stock_polling()
        self._stop_crypto_polling()
        self._cleanup_fetch()
        self._live_aggregator.reset()

    # ------------------------------------------------------------------
    # Stock polling
    # ------------------------------------------------------------------

    def _start_stock_polling(self, ticker: str) -> None:
        """Start polling timer for stock live updates via Yahoo Finance."""
        self._stop_stock_polling()

        self._stock_poll_timer = QTimer(self)
        self._stock_poll_timer.timeout.connect(self._on_stock_poll_tick)
        self._stock_poll_timer.start(self._POLL_INTERVAL_MS)
        QTimer.singleShot(0, self._on_stock_poll_tick)

    def _stop_stock_polling(self) -> None:
        """Stop the stock polling timer."""
        if self._stock_poll_timer is not None:
            self._stock_poll_timer.stop()
            self._stock_poll_timer.deleteLater()
            self._stock_poll_timer = None

    def _on_stock_poll_tick(self) -> None:
        """Handle stock polling timer tick."""
        ticker = self._get_ticker()
        if not ticker or is_crypto_ticker(ticker):
            return

        if not is_market_open_extended():
            self._stop_stock_polling()
            return

        if self._get_interval().lower() != "daily":
            return

        self._fetch_today_bar(ticker)

    # ------------------------------------------------------------------
    # Crypto polling
    # ------------------------------------------------------------------

    def _start_crypto_polling(self, ticker: str) -> None:
        """Start polling timer for crypto live updates via Yahoo Finance."""
        self._stop_crypto_polling()

        self._crypto_poll_timer = QTimer(self)
        self._crypto_poll_timer.timeout.connect(self._on_crypto_poll_tick)
        self._crypto_poll_timer.start(self._POLL_INTERVAL_MS)
        QTimer.singleShot(0, self._on_crypto_poll_tick)

    def _stop_crypto_polling(self) -> None:
        """Stop the crypto polling timer."""
        if self._crypto_poll_timer is not None:
            self._crypto_poll_timer.stop()
            self._crypto_poll_timer.deleteLater()
            self._crypto_poll_timer = None

    def _on_crypto_poll_tick(self) -> None:
        """Handle crypto polling timer tick."""
        ticker = self._get_ticker()
        if not ticker or not is_crypto_ticker(ticker):
            return

        if self._get_interval().lower() != "daily":
            return

        self._fetch_today_bar(ticker)

    # ------------------------------------------------------------------
    # Shared fetch — uses QThread for thread-safe signal delivery
    # ------------------------------------------------------------------

    def _fetch_today_bar(self, ticker: str) -> None:
        """Fetch today's OHLCV bar in a QThread (not a daemon thread)."""
        if self._fetch_in_progress:
            return

        self._fetch_in_progress = True
        self._fetch_ticker = ticker

        self._fetch_thread = QThread()
        self._fetch_worker = CalculationWorker(
            YahooFinanceService.fetch_today_ohlcv, ticker
        )
        self._fetch_worker.moveToThread(self._fetch_thread)

        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_thread.finished.connect(self._on_fetch_done, Qt.QueuedConnection)
        self._fetch_thread.start()

    def _on_fetch_done(self) -> None:
        """Handle fetch completion on main thread via QThread.finished."""
        worker = self._fetch_worker
        ticker = self._fetch_ticker
        self._cleanup_fetch()
        self._fetch_in_progress = False

        if worker is not None and worker.result is not None:
            today_bar = worker.result
            if not today_bar.empty and ticker:
                self.bar_received.emit(ticker, today_bar)

    def _cleanup_fetch(self) -> None:
        """Clean up fetch thread/worker."""
        if self._fetch_thread is not None:
            thread = self._fetch_thread
            worker = self._fetch_worker
            thread.quit()

            from app.ui.modules.base_module import _global_orphaned_threads
            _global_orphaned_threads.append(thread)

            if worker is not None:
                _global_orphaned_threads.append(worker)

            def _on_done(t=thread, w=worker):
                try:
                    _global_orphaned_threads.remove(t)
                except ValueError:
                    pass
                if w is not None:
                    try:
                        _global_orphaned_threads.remove(w)
                    except ValueError:
                        pass

            thread.finished.connect(_on_done, Qt.QueuedConnection)
        self._fetch_thread = None
        self._fetch_worker = None

    # ------------------------------------------------------------------
    # Legacy WebSocket handler (kept for future use)
    # ------------------------------------------------------------------

    def handle_live_bar(self, ticker: str, bar_data: dict):
        """
        Handle incoming minute bar from WebSocket.

        Aggregates minute bars into a daily bar via LiveBarAggregator
        and emits bar_received when the daily bar updates.
        """
        daily_bar = self._live_aggregator.add_minute_bar(bar_data)
        if daily_bar is not None:
            self.bar_received.emit(ticker, daily_bar)
