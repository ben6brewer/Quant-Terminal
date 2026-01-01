"""Auto-Fill Service - Background fetching for execution prices and ticker names.

This service handles background thread fetching of prices and names with
thread-safe signal emission for UI updates.
"""

import threading
from datetime import datetime
from typing import Callable, Dict, Optional, Set

from PySide6.QtCore import QObject, Signal

from ..services.portfolio_service import PortfolioService


class AutoFillService(QObject):
    """
    Service for auto-filling execution prices and ticker names.

    Features:
    - Background thread fetching (no UI lag)
    - Thread-safe signal emission for UI updates
    - Name caching to reduce network calls
    - User-entered tracking to avoid overwriting manual input
    """

    # Signals for thread-safe UI updates (row, value)
    price_ready = Signal(int, float)
    name_ready = Signal(int, str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._cached_names: Dict[str, str] = {}
        self._user_entered_rows: Set[int] = set()

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    def get_cached_name(self, ticker: str) -> Optional[str]:
        """
        Get cached name for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Cached name, or None if not cached
        """
        return self._cached_names.get(ticker.upper())

    def update_name_cache(self, names: Dict[str, str]) -> None:
        """
        Update name cache with multiple entries.

        Args:
            names: Dict of ticker -> name
        """
        for ticker, name in names.items():
            self._cached_names[ticker.upper()] = name

    def clear_name_cache(self) -> None:
        """Clear all cached names."""
        self._cached_names.clear()

    @property
    def cached_names(self) -> Dict[str, str]:
        """Get the full name cache (read-only copy)."""
        return dict(self._cached_names)

    # -------------------------------------------------------------------------
    # User Input Tracking
    # -------------------------------------------------------------------------

    def mark_user_entered(self, row: int) -> None:
        """
        Mark that user manually entered a price for this row.
        Auto-fill will not overwrite this row.

        Args:
            row: Row index
        """
        self._user_entered_rows.add(row)

    def clear_user_entered(self, row: int) -> None:
        """
        Clear user-entered flag for a row.

        Args:
            row: Row index
        """
        self._user_entered_rows.discard(row)

    def is_user_entered(self, row: int) -> bool:
        """
        Check if user manually entered a price for this row.

        Args:
            row: Row index

        Returns:
            True if user manually entered price
        """
        return row in self._user_entered_rows

    def clear_all_user_entered(self) -> None:
        """Clear all user-entered flags."""
        self._user_entered_rows.clear()

    # -------------------------------------------------------------------------
    # Price Auto-Fill
    # -------------------------------------------------------------------------

    def fetch_execution_price(
        self,
        row: int,
        ticker: str,
        date: str,
        is_blank_row: bool = True,
    ) -> None:
        """
        Fetch execution price in background thread.

        Emits price_ready signal when done (thread-safe UI update).

        Args:
            row: Row index
            ticker: Ticker symbol
            date: Transaction date (YYYY-MM-DD)
            is_blank_row: Whether this is the blank entry row
        """
        if not ticker or not date:
            return

        # Don't auto-fill if user manually entered a price
        if self.is_user_entered(row):
            return

        ticker_upper = ticker.upper()

        # FREE CASH is always $1.00 - no network call needed
        if ticker_upper == PortfolioService.FREE_CASH_TICKER:
            self.price_ready.emit(row, 1.0)
            return

        today_str = datetime.now().strftime("%Y-%m-%d")

        def fetch_and_emit():
            """Background thread: fetch price, then emit signal."""
            try:
                if date == today_str:
                    prices = PortfolioService.fetch_current_prices([ticker_upper])
                    price = prices.get(ticker_upper)
                else:
                    results = PortfolioService.fetch_historical_closes_batch(
                        [(ticker_upper, date)]
                    )
                    price = results.get(ticker_upper, {}).get(date)

                if price is not None:
                    self.price_ready.emit(row, price)
            except Exception:
                pass  # Silently fail

        thread = threading.Thread(target=fetch_and_emit, daemon=True)
        thread.start()

    # -------------------------------------------------------------------------
    # Name Auto-Fill
    # -------------------------------------------------------------------------

    def fetch_ticker_name(self, row: int, ticker: str) -> None:
        """
        Fetch ticker name in background thread.

        Emits name_ready signal when done (thread-safe UI update).

        Args:
            row: Row index
            ticker: Ticker symbol
        """
        if not ticker:
            return

        ticker_upper = ticker.upper()

        # FREE CASH gets special name - no network call
        if ticker_upper == PortfolioService.FREE_CASH_TICKER:
            self.name_ready.emit(row, "FREE CASH")
            return

        # Check cache first
        if ticker_upper in self._cached_names:
            self.name_ready.emit(row, self._cached_names[ticker_upper])
            return

        def fetch_and_emit():
            """Background thread: fetch name, then emit signal."""
            try:
                names = PortfolioService.fetch_ticker_names([ticker_upper])
                name = names.get(ticker_upper, "")
                if name:
                    self._cached_names[ticker_upper] = name
                    self.name_ready.emit(row, name)
            except Exception:
                pass  # Silently fail

        thread = threading.Thread(target=fetch_and_emit, daemon=True)
        thread.start()

    def fetch_names_batch(self, tickers: list) -> None:
        """
        Fetch multiple ticker names in background (for bulk updates).

        Updates cache and emits name_ready for each ticker.
        Caller should track which rows need updates.

        Args:
            tickers: List of ticker symbols
        """
        if not tickers:
            return

        # Filter out already cached and FREE CASH
        to_fetch = []
        for ticker in tickers:
            ticker_upper = ticker.upper()
            if ticker_upper == PortfolioService.FREE_CASH_TICKER:
                continue
            if ticker_upper not in self._cached_names:
                to_fetch.append(ticker_upper)

        if not to_fetch:
            return

        def fetch_batch():
            try:
                names = PortfolioService.fetch_ticker_names(to_fetch)
                for ticker, name in names.items():
                    if name:
                        self._cached_names[ticker.upper()] = name
            except Exception:
                pass

        thread = threading.Thread(target=fetch_batch, daemon=True)
        thread.start()

    # -------------------------------------------------------------------------
    # Row Adjustment (for sorts/inserts)
    # -------------------------------------------------------------------------

    def adjust_rows_after_insert(self, from_row: int, count: int = 1) -> None:
        """
        Adjust user-entered tracking after row insertion.

        Args:
            from_row: Row where insert happened
            count: Number of rows inserted
        """
        new_set: Set[int] = set()
        for row in self._user_entered_rows:
            if row >= from_row:
                new_set.add(row + count)
            else:
                new_set.add(row)
        self._user_entered_rows = new_set

    def adjust_rows_after_delete(self, deleted_row: int) -> None:
        """
        Adjust user-entered tracking after row deletion.

        Args:
            deleted_row: Row that was deleted
        """
        self._user_entered_rows.discard(deleted_row)
        new_set: Set[int] = set()
        for row in self._user_entered_rows:
            if row > deleted_row:
                new_set.add(row - 1)
            else:
                new_set.add(row)
        self._user_entered_rows = new_set
