from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from app.core.config import (
    INTERVAL_MAP,
    DEFAULT_PERIOD,
    DATA_FETCH_THREADS,
    SHOW_DOWNLOAD_PROGRESS,
    ERROR_EMPTY_TICKER,
    ERROR_NO_DATA,
    YAHOO_HISTORICAL_START,
)

if TYPE_CHECKING:
    import pandas as pd


# ============================================================================
# Batch Processing Types
# ============================================================================


class TickerGroup(Enum):
    """Classification groups for batch ticker processing."""

    CACHE_CURRENT = "cache_current"  # Cache is up-to-date, just read
    NEEDS_UPDATE = "needs_update"  # Need Yahoo full history fetch


@dataclass
class TickerClassification:
    """Classification result for a single ticker."""

    group: TickerGroup
    ticker: str
    cached_df: Optional["pd.DataFrame"] = None

# Import the cache manager
from app.services.market_data_cache import MarketDataCache

# Import Yahoo Finance service (sole data provider)
from app.services.yahoo_finance_service import YahooFinanceService

# Import crypto detection utility
from app.utils.market_hours import is_crypto_ticker

# Create a global cache instance (disk-based parquet cache)
_cache = MarketDataCache()

# Data source version tracking - increment when switching data sources
# to automatically clear cache and avoid mixing data from different providers
_DATA_SOURCE_VERSION = "yahoo_v2"
_VERSION_FILE = Path.home() / ".quant_terminal" / "cache" / ".data_source_version"


def _check_data_source_version() -> None:
    """
    Check if data source has changed and clear cache if needed.

    This ensures we don't mix data from different providers
    which could have different adjusted prices or date ranges.
    """
    _VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    if _VERSION_FILE.exists():
        current = _VERSION_FILE.read_text().strip()
        if current == _DATA_SOURCE_VERSION:
            return

    print(f"Data source changed to {_DATA_SOURCE_VERSION}, clearing cache...")
    _cache.clear_cache()
    _VERSION_FILE.write_text(_DATA_SOURCE_VERSION)

# In-memory session cache to avoid repeated parquet reads
# Key: ticker (uppercase), Value: DataFrame
_memory_cache: Dict[str, Any] = {}
_memory_cache_lock = threading.Lock()

# Live bar cache for today's partial data
# Key: ticker, Value: {"df": DataFrame, "timestamp": float}
_live_bar_cache: Dict[str, Any] = {}
_live_bar_cache_lock = threading.Lock()
_LIVE_BAR_REFRESH_SECONDS = 900  # 15 minutes


def _get_from_memory_cache(ticker: str) -> Optional["pd.DataFrame"]:
    """Get DataFrame from memory cache (thread-safe)."""
    with _memory_cache_lock:
        return _memory_cache.get(ticker)


def _set_memory_cache(ticker: str, df: "pd.DataFrame") -> None:
    """Set DataFrame in memory cache (thread-safe)."""
    with _memory_cache_lock:
        _memory_cache[ticker] = df


def _get_live_bar(ticker: str) -> Optional["pd.DataFrame"]:
    """
    Get today's partial (live) bar for a ticker via Yahoo Finance.

    Uses a 15-minute cache to avoid excessive API calls.

    Args:
        ticker: Ticker symbol

    Returns:
        DataFrame with today's partial bar, or None if unavailable
    """
    import time

    ticker = ticker.upper()

    # Check cache first
    with _live_bar_cache_lock:
        cached = _live_bar_cache.get(ticker)
        if cached:
            elapsed = time.time() - cached["timestamp"]
            if elapsed < _LIVE_BAR_REFRESH_SECONDS:
                return cached["df"]

    # Fetch fresh live bar from Yahoo
    live_bar = YahooFinanceService.fetch_today_ohlcv(ticker)

    # Cache the result (even if None)
    with _live_bar_cache_lock:
        _live_bar_cache[ticker] = {
            "df": live_bar,
            "timestamp": time.time(),
        }

    return live_bar


def _append_live_bar(df: "pd.DataFrame", ticker: str) -> "pd.DataFrame":
    """
    Append live bar to daily data if available.

    Only appends if:
    - Live bar is available
    - The live bar's date is not already in the DataFrame

    Args:
        df: DataFrame with daily OHLCV data
        ticker: Ticker symbol

    Returns:
        DataFrame with live bar appended (if applicable)
    """
    import pandas as pd

    live_bar = _get_live_bar(ticker)
    if live_bar is None or live_bar.empty:
        return df

    # Get the date of the live bar
    live_bar_date = live_bar.index[0].date()
    last_cached_date = df.index.max().date()

    # Only append if live bar date is newer than cached data
    if live_bar_date <= last_cached_date:
        return df

    # Append live bar
    combined = pd.concat([df, live_bar])
    combined.sort_index(inplace=True)

    return combined


def _load_btc_historical_csv() -> "pd.DataFrame":
    """Load historical BTC data from CSV for pre-Yahoo-Finance dates."""
    import pandas as pd
    from pathlib import Path

    csv_path = Path(__file__).parent / "bitcoin_historical_prices.csv"
    if not csv_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")
    # Capitalize column names to match yfinance format
    df.columns = [c.capitalize() for c in df.columns]
    df.index.name = None
    df.sort_index(inplace=True)
    return df


def _prepend_btc_historical(yf_df: "pd.DataFrame") -> "pd.DataFrame":
    """Prepend historical CSV data to BTC-USD Yahoo Finance data."""
    import pandas as pd

    csv_df = _load_btc_historical_csv()
    if csv_df.empty:
        return yf_df

    # Get first date from Yahoo Finance data
    first_yf_date = yf_df.index.min()

    # Filter CSV to dates BEFORE Yahoo Finance starts
    csv_before = csv_df[csv_df.index < first_yf_date]

    if csv_before.empty:
        return yf_df

    # Concatenate: CSV first, then Yahoo Finance
    combined = pd.concat([csv_before, yf_df])
    combined.sort_index(inplace=True)
    return combined


# ============================================================================
# Batch Processing Functions
# ============================================================================


def classify_tickers(
    tickers: List[str],
) -> Dict[TickerGroup, List[TickerClassification]]:
    """
    Classify tickers into processing groups based on cache state.

    Groups:
    - CACHE_CURRENT: Cache exists and is up-to-date
    - NEEDS_UPDATE: No cache or cache is outdated

    Args:
        tickers: List of ticker symbols

    Returns:
        Dict mapping TickerGroup -> list of TickerClassification
    """
    groups: Dict[TickerGroup, List[TickerClassification]] = {
        TickerGroup.CACHE_CURRENT: [],
        TickerGroup.NEEDS_UPDATE: [],
    }

    for ticker in tickers:
        ticker = ticker.strip().upper()

        # Check memory cache first
        df = _get_from_memory_cache(ticker)
        if df is not None and not df.empty and _cache.is_cache_current(ticker):
            groups[TickerGroup.CACHE_CURRENT].append(
                TickerClassification(TickerGroup.CACHE_CURRENT, ticker, df)
            )
            continue

        # Check disk cache
        if _cache.has_cache(ticker) and _cache.is_cache_current(ticker):
            cached_df = _cache.get_cached_data(ticker)
            if cached_df is not None and not cached_df.empty:
                groups[TickerGroup.CACHE_CURRENT].append(
                    TickerClassification(TickerGroup.CACHE_CURRENT, ticker, cached_df)
                )
                continue

        # Need to fetch from Yahoo
        groups[TickerGroup.NEEDS_UPDATE].append(
            TickerClassification(TickerGroup.NEEDS_UPDATE, ticker, None)
        )

    return groups


def fetch_price_history_batch(
    tickers: List[str],
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
) -> Dict[str, "pd.DataFrame"]:
    """
    Fetch price history for multiple tickers with batch optimization.

    Classifies tickers into two groups and processes each optimally:
    - Group A (Cache Current): Direct parquet reads
    - Group B (Needs Update): Single batch yf.download()

    Args:
        tickers: List of ticker symbols
        progress_callback: Optional callback(completed, total, ticker, phase)
                          phase is one of: "classifying", "cache", "yahoo"

    Returns:
        Dict mapping ticker -> DataFrame with OHLCV data
    """
    import pandas as pd

    if not tickers:
        return {}

    # Ensure unique, uppercase tickers
    tickers = list(dict.fromkeys(t.strip().upper() for t in tickers))
    total = len(tickers)

    print(f"\n=== Batch fetching {total} tickers ===")

    results: Dict[str, pd.DataFrame] = {}

    # Phase 1: Classification
    if progress_callback:
        progress_callback(0, total, "", "classifying")

    groups = classify_tickers(tickers)

    group_a = groups[TickerGroup.CACHE_CURRENT]
    group_b = groups[TickerGroup.NEEDS_UPDATE]

    print(f"  Group A (cache current): {len(group_a)} tickers")
    print(f"  Group B (need Yahoo): {len(group_b)} tickers")

    # Phase 2: Process Group A (Cache Current) - just return cached data
    if group_a:
        print(f"\nReading {len(group_a)} tickers from cache...")
        for i, classification in enumerate(group_a):
            results[classification.ticker] = classification.cached_df
            _set_memory_cache(classification.ticker, classification.cached_df)
            if progress_callback:
                progress_callback(i + 1, len(group_a), classification.ticker, "cache")

    # Phase 3: Process Group B (Needs Update) - batch Yahoo download
    if group_b:
        batch_tickers = [c.ticker for c in group_b]

        def yahoo_progress(completed: int, yahoo_total: int, ticker: str) -> None:
            if progress_callback:
                progress_callback(completed, yahoo_total, ticker, "yahoo")

        yahoo_results, failed = YahooFinanceService.fetch_batch_full_history(
            batch_tickers, yahoo_progress
        )

        # Process successful Yahoo results
        for classification in group_b:
            ticker = classification.ticker
            if ticker in yahoo_results:
                df = yahoo_results[ticker]

                # Prepend BTC historical CSV if needed
                if ticker == "BTC-USD":
                    df = _prepend_btc_historical(df)

                # Save to caches
                _cache.save_to_cache(ticker, df)
                _set_memory_cache(ticker, df)

                results[ticker] = df
            elif ticker in failed:
                print(f"  {ticker}: Yahoo failed, no data available")

    print(f"\n=== Batch complete: {len(results)}/{total} tickers loaded ===\n")
    return results


def fetch_price_history(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = "1d",
    skip_live_bar: bool = False,
) -> "pd.DataFrame":
    """
    Fetch historical price data for a ticker with two-level caching.

    Data flow:
    1. Check memory cache -> if current, return
    2. Check parquet cache -> if current, return
    3. Fetch full history from Yahoo Finance
    4. Prepend BTC CSV if applicable
    5. Save to cache and return

    Args:
        ticker: Ticker symbol (e.g., "BTC-USD", "AAPL")
        period: Time period (e.g., "max", "1y", "6mo")
        interval: Data interval (e.g., "1d", "daily", "weekly")
        skip_live_bar: If True, skip fetching today's live bar.
            Use this for portfolio operations that don't need intraday precision.

    Returns:
        DataFrame with OHLCV data

    Raises:
        ValueError: If ticker is empty or no data is available
    """
    import pandas as pd

    # Check if data source has changed (auto-clears cache if switching providers)
    _check_data_source_version()

    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError(ERROR_EMPTY_TICKER)

    interval_key = (interval or "1d").strip().lower()
    yf_interval = INTERVAL_MAP.get(interval_key, "1d")

    # Check if we need daily data based on ORIGINAL interval_key (before modification)
    needs_daily = interval_key in ["daily", "1d"]

    # Special handling for yearly interval
    if yf_interval == "1y":
        yf_interval = "1d"  # We'll resample from daily data

    # Helper to append live data
    def _append_live_data(data: "pd.DataFrame") -> "pd.DataFrame":
        """Append today's data from Yahoo Finance."""
        if skip_live_bar:
            return data
        return _append_live_bar(data, ticker)

    # Helper to return data with appropriate resampling
    def _return_data(data: "pd.DataFrame") -> "pd.DataFrame":
        """Return data with live append and resampling if needed."""
        df_with_live = _append_live_data(data)
        if needs_daily:
            return df_with_live
        return _resample_data(df_with_live, interval_key)

    # LEVEL 1: Check memory cache first (instant, no disk I/O)
    df = _get_from_memory_cache(ticker)
    if df is not None and not df.empty:
        if _cache.is_cache_current(ticker):
            return _return_data(df)

    # LEVEL 2: Check disk cache (parquet)
    if _cache.has_cache(ticker):
        df = _cache.get_cached_data(ticker)
        if df is not None and not df.empty:
            if _cache.is_cache_current(ticker):
                last_date = df.index.max().strftime("%Y-%m-%d")
                print(f"Using cached data for {ticker} (last date: {last_date})")
                _set_memory_cache(ticker, df)
                return _return_data(df)

    # LEVEL 3: No current cache - fetch full history from Yahoo Finance
    print(f"Fetching {ticker} from Yahoo Finance...")
    df, was_rate_limited = YahooFinanceService.fetch_full_history_safe(ticker)

    if not was_rate_limited and df is not None and not df.empty:
        df = df.copy()
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        # Prepend historical CSV data for BTC-USD
        if ticker == "BTC-USD":
            df = _prepend_btc_historical(df)

        # Save to caches
        _cache.save_to_cache(ticker, df)
        _set_memory_cache(ticker, df)

        print(f"Fetched {len(df)} bars for {ticker} from Yahoo Finance")
        return _return_data(df)

    # Yahoo failed - try any stale cached data as last resort
    if _cache.has_cache(ticker):
        df = _cache.get_cached_data(ticker)
        if df is not None and not df.empty:
            last_date = df.index.max().strftime("%Y-%m-%d")
            print(f"Using outdated cached data for {ticker} (last date: {last_date})")
            _set_memory_cache(ticker, df)
            return _return_data(df)

    # No data available
    raise ValueError(ERROR_NO_DATA.format(ticker=ticker))


def _resample_data(df: "pd.DataFrame", interval_key: str) -> "pd.DataFrame":
    """
    Resample daily data to the requested interval.

    Args:
        df: DataFrame with daily OHLCV data
        interval_key: Interval key (e.g., "weekly", "monthly", "yearly")

    Returns:
        Resampled DataFrame
    """
    if interval_key in ["1d", "daily"]:
        return df

    # Define resampling rules
    resample_rules = {
        "weekly": "W",
        "1wk": "W",
        "monthly": "ME",
        "1mo": "ME",
        "yearly": "YE",
        "1y": "YE",
    }

    resample_freq = resample_rules.get(interval_key)

    if resample_freq is None:
        # Unknown interval, return daily data
        return df

    # OHLCV aggregation
    ohlc = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
    }
    if "Volume" in df.columns:
        ohlc["Volume"] = "sum"

    # Resample
    df_resampled = df.resample(resample_freq).agg(ohlc).dropna(how="any")

    return df_resampled


def clear_cache(ticker: str | None = None) -> None:
    """
    Clear cache for a specific ticker or all tickers.

    Clears memory cache and disk cache.

    Args:
        ticker: Ticker symbol to clear, or None to clear all
    """
    # Clear memory cache
    with _memory_cache_lock:
        if ticker:
            _memory_cache.pop(ticker.upper(), None)
        else:
            _memory_cache.clear()

    # Clear disk cache
    _cache.clear_cache(ticker)


def fetch_price_history_yahoo(
    ticker: str,
    period: str = "max",
    interval: str = "1d",
) -> "pd.DataFrame":
    """
    Fetch price history using Yahoo Finance exclusively.

    Used by chart module. Checks parquet first, fetches if needed.

    Flow:
    1. Check memory cache -> if current, return
    2. Check parquet cache -> if current, return
    3. If outdated -> incremental Yahoo update
    4. If no parquet -> fresh Yahoo fetch
    5. Save/update parquet

    Args:
        ticker: Ticker symbol (e.g., "BTC-USD", "AAPL")
        period: Time period (e.g., "max", "1y", "6mo") - only "max" fully supported
        interval: Data interval (e.g., "1d", "daily", "weekly")

    Returns:
        DataFrame with OHLCV data

    Raises:
        ValueError: If ticker is empty or no data is available
    """
    import pandas as pd
    from datetime import datetime, timedelta

    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError(ERROR_EMPTY_TICKER)

    interval_key = (interval or "1d").strip().lower()
    needs_daily = interval_key in ["daily", "1d"]

    # LEVEL 1: Check memory cache first
    df = _get_from_memory_cache(ticker)
    if df is not None and not df.empty:
        if _cache.is_cache_current(ticker):
            if needs_daily:
                return df
            return _resample_data(df, interval_key)

    # LEVEL 2: Check if parquet exists
    if _cache.has_cache(ticker):
        df = _cache.get_cached_data(ticker)
        if df is not None and not df.empty:
            last_date = df.index.max().strftime("%Y-%m-%d")
            print(f"Found cached data for {ticker} (last date: {last_date})")

            # Check if incremental update needed
            if not _cache.is_cache_current(ticker):
                print(f"Updating {ticker} with recent Yahoo data...")
                df = _perform_yahoo_incremental_update(ticker, df)
                _cache.save_to_cache(ticker, df)

            _set_memory_cache(ticker, df)

            if needs_daily:
                return df
            return _resample_data(df, interval_key)

    # LEVEL 3: Fresh fetch from Yahoo Finance (no parquet exists)
    print(f"Fresh fetch for {ticker} from Yahoo Finance...")
    df = YahooFinanceService.fetch_full_history(ticker)

    if df is None or df.empty:
        raise ValueError(ERROR_NO_DATA.format(ticker=ticker))

    # Save to cache
    _cache.save_to_cache(ticker, df)
    _set_memory_cache(ticker, df)

    if needs_daily:
        return df
    return _resample_data(df, interval_key)


def _perform_yahoo_incremental_update(ticker: str, cached_df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Fetch missing recent days from Yahoo Finance.

    Args:
        ticker: Ticker symbol
        cached_df: Existing cached DataFrame

    Returns:
        Updated DataFrame with new data appended
    """
    import pandas as pd
    from datetime import datetime, timedelta

    # Get last cached date
    last_date = cached_df.index.max().date()

    # Calculate date range for update
    start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # If start > end, no update needed
    if start_date > end_date:
        return cached_df

    print(f"Fetching Yahoo data for {ticker}: {start_date} to {end_date}")

    # Fetch missing days from Yahoo
    try:
        new_df = YahooFinanceService.fetch_historical(ticker, start_date, end_date)
    except Exception as e:
        print(f"Yahoo incremental update failed for {ticker}: {e}")
        return cached_df

    # If no new data, return cached
    if new_df is None or new_df.empty:
        print(f"No new Yahoo data for {ticker}")
        return cached_df

    # Append and deduplicate
    combined = pd.concat([cached_df, new_df])
    combined = combined[~combined.index.duplicated(keep='last')]
    combined.sort_index(inplace=True)

    print(f"Updated {ticker} with {len(new_df)} new bars from Yahoo")
    return combined
