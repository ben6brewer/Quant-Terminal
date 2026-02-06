"""
Yahoo Finance service - sole data provider for all market data.

Provides:
1. Full historical data for all tickers (stocks, crypto, ETFs)
2. Batch fetching for portfolios and large ticker lists
3. Today's OHLCV for live polling (stocks and crypto)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    import pandas as pd


class YahooFinanceService:
    """
    Service for fetching market data from Yahoo Finance.

    This is the sole data provider for all market data. Features:
    - Full historical data for any ticker
    - Batch downloading for portfolios and large ticker lists
    - Today's OHLCV for live polling
    - Chunked parallel downloads for 1000+ ticker batches

    All methods use lazy imports for startup performance.
    """

    @classmethod
    def fetch_historical(
        cls,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> "pd.DataFrame":
        """
        Fetch historical OHLCV data from Yahoo Finance.

        Args:
            ticker: Ticker symbol (Yahoo format, e.g., "AAPL", "BTC-USD")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            DataFrame with OHLCV columns and DatetimeIndex.
            Returns empty DataFrame if no data available.

        Note:
            This method fails silently if Yahoo doesn't have data for the
            requested range. It returns an empty DataFrame in that case.
        """
        import pandas as pd
        import yfinance as yf

        ticker = ticker.strip().upper()

        try:
            # Fetch data from Yahoo Finance
            df = yf.download(
                tickers=ticker,
                start=start_date,
                end=end_date,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=1,
            )

            if df is None or df.empty:
                return pd.DataFrame()

            # Handle MultiIndex columns (yfinance sometimes returns these)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            # Ensure standard column names
            df = cls._normalize_columns(df)

            # Ensure DatetimeIndex
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)

            return df

        except Exception as e:
            # Fail silently - return empty DataFrame
            print(f"Yahoo Finance fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    @classmethod
    def fetch_today_ohlcv(cls, ticker: str) -> Optional["pd.DataFrame"]:
        """
        Fetch today's OHLCV bar for a ticker.

        Used for live polling of both stocks and crypto tickers.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "BTC-USD")

        Returns:
            DataFrame with single row for today, or None if unavailable
        """
        import pandas as pd
        import yfinance as yf

        ticker = ticker.strip().upper()

        try:
            # Fetch last 5 days to ensure we get today's data
            # (sometimes Yahoo has a lag, so we fetch a few days)
            df = yf.download(
                tickers=ticker,
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=1,
            )

            if df is None or df.empty:
                return None

            # Handle MultiIndex columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            # Normalize columns
            df = cls._normalize_columns(df)

            # Ensure DatetimeIndex
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)

            # Get the most recent bar (should be today or most recent trading day)
            if not df.empty:
                # Return only the last row
                last_bar = df.iloc[[-1]].copy()
                return last_bar

            return None

        except Exception as e:
            print(f"Yahoo Finance today fetch failed for {ticker}: {e}")
            return None

    @classmethod
    def _normalize_columns(cls, df: "pd.DataFrame") -> "pd.DataFrame":
        """
        Normalize DataFrame columns to standard OHLCV format.

        Ensures columns are: Open, High, Low, Close, Volume

        Args:
            df: DataFrame with various column name formats

        Returns:
            DataFrame with normalized column names
        """
        # Map of possible column names to standard names
        column_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "adj close": "Adj Close",
            "adj_close": "Adj Close",
        }

        # Rename columns (case-insensitive)
        new_columns = {}
        for col in df.columns:
            col_lower = col.lower().strip()
            if col_lower in column_map:
                new_columns[col] = column_map[col_lower]

        if new_columns:
            df = df.rename(columns=new_columns)

        # Keep only OHLCV columns
        standard_cols = ["Open", "High", "Low", "Close", "Volume"]
        available_cols = [c for c in standard_cols if c in df.columns]
        df = df[available_cols]

        return df

    @classmethod
    def fetch_full_history(cls, ticker: str) -> "pd.DataFrame":
        """
        Fetch maximum available history from Yahoo Finance.

        Used for fresh ticker loads in chart module when no parquet exists.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "BTC-USD")

        Returns:
            DataFrame with OHLCV columns and DatetimeIndex.
            Returns empty DataFrame if no data available.
        """
        import pandas as pd
        import yfinance as yf

        ticker = ticker.strip().upper()

        try:
            print(f"Fetching full history for {ticker} from Yahoo Finance...")

            # Fetch maximum history
            df = yf.download(
                tickers=ticker,
                period="max",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=1,
            )

            if df is None or df.empty:
                print(f"No data returned from Yahoo Finance for {ticker}")
                return pd.DataFrame()

            # Handle MultiIndex columns (yfinance sometimes returns these)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            # Ensure standard column names
            df = cls._normalize_columns(df)

            # Ensure DatetimeIndex
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)

            print(f"Fetched {len(df)} bars for {ticker} from Yahoo Finance")

            # Also cache metadata (name, sector, etc.) for this ticker
            try:
                from app.services.ticker_metadata_service import TickerMetadataService

                TickerMetadataService.get_metadata(ticker)
            except Exception as meta_err:
                # Don't fail the fetch if metadata caching fails
                print(f"Warning: Could not cache metadata for {ticker}: {meta_err}")

            return df

        except Exception as e:
            print(f"Yahoo Finance full history fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    @classmethod
    def fetch_full_history_safe(
        cls, ticker: str
    ) -> tuple["pd.DataFrame", bool]:
        """
        Fetch full history with rate limit detection.

        This method wraps fetch_full_history() and detects rate limiting
        by checking for empty responses or exceptions.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "BTC-USD")

        Returns:
            Tuple of (DataFrame, was_rate_limited):
            - If successful: (DataFrame with data, False)
            - If rate limited: (empty DataFrame, True)
        """
        import pandas as pd

        try:
            df = cls.fetch_full_history(ticker)

            # Empty DataFrame indicates rate limiting or invalid ticker
            if df is None or df.empty:
                return (pd.DataFrame(), True)

            return (df, False)

        except Exception as e:
            # Any exception is treated as rate limiting
            print(f"Yahoo Finance rate limited or failed for {ticker}: {e}")
            return (pd.DataFrame(), True)

    @classmethod
    def fetch_batch_full_history(
        cls,
        tickers: list[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> tuple[dict[str, "pd.DataFrame"], list[str]]:
        """
        Fetch full history for multiple tickers using chunked parallel downloads.

        For small lists (<=200), uses a single yf.download() call.
        For large lists (>200, e.g. 3000+ IWV constituents), chunks into
        groups of 200 and runs parallel yf.download() calls via ThreadPoolExecutor.

        Args:
            tickers: List of ticker symbols
            progress_callback: Optional callback(completed, total, current_ticker)

        Returns:
            Tuple of:
            - Dict mapping ticker -> DataFrame with OHLCV data
            - List of failed tickers
        """
        import pandas as pd

        if not tickers:
            return {}, []

        # Normalize and deduplicate tickers
        tickers = list(dict.fromkeys(t.strip().upper() for t in tickers))
        total = len(tickers)

        print(f"Batch fetching {total} tickers from Yahoo Finance...")

        _CHUNK_SIZE = 200

        if total <= _CHUNK_SIZE:
            # Small batch - single download
            results, failed = cls._fetch_batch_chunk(tickers, progress_callback)
        else:
            # Large batch - chunked parallel downloads
            from concurrent.futures import ThreadPoolExecutor, as_completed

            chunks = [tickers[i:i + _CHUNK_SIZE] for i in range(0, total, _CHUNK_SIZE)]
            print(f"  Splitting into {len(chunks)} chunks of ~{_CHUNK_SIZE} tickers")

            results: dict[str, pd.DataFrame] = {}
            failed: list[str] = []
            completed_count = 0

            def fetch_chunk(chunk: list[str]) -> tuple[dict[str, pd.DataFrame], list[str]]:
                return cls._fetch_batch_chunk(chunk)

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(fetch_chunk, chunk): chunk for chunk in chunks}
                for future in as_completed(futures):
                    try:
                        chunk_results, chunk_failed = future.result()
                        results.update(chunk_results)
                        failed.extend(chunk_failed)
                        completed_count += len(chunk_results) + len(chunk_failed)
                        if progress_callback:
                            last_ticker = list(chunk_results.keys())[-1] if chunk_results else ""
                            progress_callback(completed_count, total, last_ticker)
                    except Exception as e:
                        chunk = futures[future]
                        print(f"  Chunk failed: {e}")
                        failed.extend(chunk)

        print(
            f"Yahoo batch complete: {len(results)} succeeded, {len(failed)} failed"
        )

        # Cache metadata for successful tickers
        if results:
            try:
                from app.services.ticker_metadata_service import TickerMetadataService

                successful_tickers = list(results.keys())
                TickerMetadataService.get_metadata_batch(successful_tickers)
                print(f"Cached metadata for {len(successful_tickers)} tickers")
            except Exception as meta_err:
                print(f"Warning: Could not cache metadata: {meta_err}")

        return results, failed

    @classmethod
    def _fetch_batch_chunk(
        cls,
        tickers: list[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> tuple[dict[str, "pd.DataFrame"], list[str]]:
        """
        Fetch full history for a chunk of tickers in a single yf.download call.

        Args:
            tickers: List of ticker symbols (should be <=200 for best results)
            progress_callback: Optional callback(completed, total, current_ticker)

        Returns:
            Tuple of (results dict, failed list)
        """
        import pandas as pd
        import yfinance as yf

        if not tickers:
            return {}, []

        total = len(tickers)

        try:
            df = yf.download(
                tickers=" ".join(tickers) if len(tickers) > 1 else tickers[0],
                period="max",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="ticker" if len(tickers) > 1 else "column",
            )

            if df is None or df.empty:
                return {}, tickers

            results: dict[str, pd.DataFrame] = {}
            failed: list[str] = []

            if len(tickers) == 1:
                ticker = tickers[0]
                try:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [c[0] for c in df.columns]

                    ticker_df = cls._normalize_columns(df.copy())
                    ticker_df.index = pd.to_datetime(ticker_df.index)
                    ticker_df.sort_index(inplace=True)
                    ticker_df.dropna(how="all", inplace=True)

                    if not ticker_df.empty:
                        results[ticker] = ticker_df
                    else:
                        failed.append(ticker)
                except Exception:
                    failed.append(ticker)

                if progress_callback:
                    progress_callback(1, 1, ticker)
            else:
                for i, ticker in enumerate(tickers):
                    try:
                        if ticker in df.columns.get_level_values(0):
                            ticker_df = df[ticker].copy()
                            ticker_df = cls._normalize_columns(ticker_df)
                            ticker_df.index = pd.to_datetime(ticker_df.index)
                            ticker_df.sort_index(inplace=True)
                            ticker_df.dropna(how="all", inplace=True)

                            if not ticker_df.empty:
                                results[ticker] = ticker_df
                            else:
                                failed.append(ticker)
                        else:
                            failed.append(ticker)
                    except Exception:
                        failed.append(ticker)

                    if progress_callback:
                        progress_callback(i + 1, total, ticker)

            return results, failed

        except Exception as e:
            print(f"Yahoo Finance batch chunk failed: {e}")
            return {}, tickers

    @classmethod
    def fetch_batch_date_range(
        cls,
        tickers: list[str],
        date_ranges: dict[str, tuple[str, str]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict[str, "pd.DataFrame"]:
        """
        Fetch historical data for multiple tickers with per-ticker date ranges.

        Groups tickers by identical date ranges and batch downloads each group.
        Used by BenchmarkReturnsService for incremental updates.

        Args:
            tickers: List of ticker symbols
            date_ranges: Dict mapping ticker -> (from_date, to_date)
            progress_callback: Optional callback(completed, total, ticker)

        Returns:
            Dict mapping ticker -> DataFrame with OHLCV data
        """
        import pandas as pd
        import yfinance as yf
        from collections import defaultdict

        if not tickers or not date_ranges:
            return {}

        # Group tickers by identical date ranges for batch efficiency
        range_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        for ticker in tickers:
            if ticker in date_ranges:
                range_key = date_ranges[ticker]
                range_groups[range_key].append(ticker)

        results: dict[str, pd.DataFrame] = {}
        completed = 0
        total = len(tickers)

        for (start_date, end_date), group_tickers in range_groups.items():
            try:
                df = yf.download(
                    tickers=" ".join(group_tickers) if len(group_tickers) > 1 else group_tickers[0],
                    start=start_date,
                    end=end_date,
                    interval="1d",
                    auto_adjust=False,
                    progress=False,
                    threads=True,
                    group_by="ticker" if len(group_tickers) > 1 else "column",
                )

                if df is None or df.empty:
                    completed += len(group_tickers)
                    continue

                if len(group_tickers) == 1:
                    ticker = group_tickers[0]
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [c[0] for c in df.columns]
                    ticker_df = cls._normalize_columns(df.copy())
                    ticker_df.index = pd.to_datetime(ticker_df.index)
                    ticker_df.sort_index(inplace=True)
                    ticker_df.dropna(how="all", inplace=True)
                    if not ticker_df.empty:
                        results[ticker] = ticker_df
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total, ticker)
                else:
                    for ticker in group_tickers:
                        try:
                            if ticker in df.columns.get_level_values(0):
                                ticker_df = df[ticker].copy()
                                ticker_df = cls._normalize_columns(ticker_df)
                                ticker_df.index = pd.to_datetime(ticker_df.index)
                                ticker_df.sort_index(inplace=True)
                                ticker_df.dropna(how="all", inplace=True)
                                if not ticker_df.empty:
                                    results[ticker] = ticker_df
                        except Exception:
                            pass
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, total, ticker)

            except Exception as e:
                print(f"Yahoo batch date range failed for group: {e}")
                completed += len(group_tickers)

        print(f"Yahoo batch date range: {len(results)}/{total} tickers fetched")
        return results

    @classmethod
    def fetch_batch_current_prices(cls, tickers: list[str]) -> dict[str, float]:
        """
        Fetch current prices for multiple tickers in a single API call.

        Used for live price updates in Portfolio Construction module.
        Returns the most recent close price for each ticker.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> latest close price
        """
        import pandas as pd
        import yfinance as yf

        if not tickers:
            return {}

        # Normalize tickers
        tickers = [t.strip().upper() for t in tickers]

        try:
            # Single batch download - fetch 5 days for redundancy
            df = yf.download(
                tickers=" ".join(tickers) if len(tickers) > 1 else tickers[0],
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="ticker" if len(tickers) > 1 else "column",
            )

            if df is None or df.empty:
                return {}

            prices: dict[str, float] = {}

            if len(tickers) == 1:
                # Single ticker - flat columns
                ticker = tickers[0]
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0] for c in df.columns]
                if "Close" in df.columns:
                    close_series = df["Close"].dropna()
                    if not close_series.empty:
                        prices[ticker] = float(close_series.iloc[-1])
            else:
                # Multiple tickers - MultiIndex columns
                for ticker in tickers:
                    try:
                        if ticker in df.columns.get_level_values(0):
                            ticker_close = df[ticker]["Close"].dropna()
                            if not ticker_close.empty:
                                prices[ticker] = float(ticker_close.iloc[-1])
                    except Exception:
                        pass  # Skip failed tickers silently

            return prices

        except Exception as e:
            print(f"Yahoo Finance batch current prices failed: {e}")
            return {}

    @classmethod
    def is_valid_ticker(cls, ticker: str) -> bool:
        """
        Check if a ticker exists on Yahoo Finance.

        Args:
            ticker: Ticker symbol

        Returns:
            True if valid, False otherwise
        """
        import yfinance as yf

        ticker = ticker.strip().upper()

        try:
            info = yf.Ticker(ticker).info
            # Check if we got valid data
            return info is not None and info.get("regularMarketPrice") is not None
        except Exception:
            return False
