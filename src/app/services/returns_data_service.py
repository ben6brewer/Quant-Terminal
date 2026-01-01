"""Returns Data Service - Cached Daily Returns for Portfolio Analysis.

This service computes and caches daily returns for portfolios, optimized
for analysis modules like Risk Analysis, Monte Carlo, and Return Distributions.
"""

import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from app.services.market_data import fetch_price_history
from app.services.portfolio_data_service import PortfolioDataService


class ReturnsDataService:
    """
    Service for computing and caching portfolio daily returns.

    Features:
    - Lazy computation: returns calculated on first access
    - Parquet caching: fast load times for 100+ securities
    - Auto-invalidation: cache invalidated when portfolio modified
    - Thread-safe: multiple modules can access concurrently
    """

    _CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "returns"
    _cache_lock = threading.Lock()

    # In-memory cache for session performance
    _memory_cache: Dict[str, pd.DataFrame] = {}
    _memory_cache_timestamps: Dict[str, datetime] = {}

    @classmethod
    def _ensure_cache_dir(cls) -> None:
        """Create cache directory if it doesn't exist."""
        cls._CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _get_cache_path(cls, portfolio_name: str) -> Path:
        """Get parquet cache path for a portfolio."""
        # Sanitize name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in portfolio_name)
        return cls._CACHE_DIR / f"{safe_name}_returns.parquet"

    @classmethod
    def _is_cache_valid(cls, portfolio_name: str) -> bool:
        """
        Check if cached returns are still valid.

        Cache is invalid if:
        - Cache file doesn't exist
        - Portfolio was modified after cache creation
        """
        cache_path = cls._get_cache_path(portfolio_name)
        if not cache_path.exists():
            return False

        # Get portfolio modification time
        portfolio_mtime = PortfolioDataService.get_portfolio_modified_time(portfolio_name)
        if portfolio_mtime is None:
            return False

        # Get cache modification time
        try:
            cache_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        except OSError:
            return False

        # Cache valid if created after portfolio was last modified
        return cache_mtime > portfolio_mtime

    @classmethod
    def get_daily_returns(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get daily returns for all tickers in a portfolio.

        Returns a DataFrame with:
        - Index: dates (DatetimeIndex)
        - Columns: ticker symbols
        - Values: daily returns (percentage as decimal, e.g., 0.05 = 5%)

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            DataFrame of daily returns, or empty DataFrame if portfolio not found
        """
        with cls._cache_lock:
            # Check memory cache first
            if portfolio_name in cls._memory_cache:
                if cls._is_cache_valid(portfolio_name):
                    df = cls._memory_cache[portfolio_name]
                    return cls._filter_date_range(df, start_date, end_date)

            # Check disk cache
            if cls._is_cache_valid(portfolio_name):
                cache_path = cls._get_cache_path(portfolio_name)
                try:
                    df = pd.read_parquet(cache_path)
                    cls._memory_cache[portfolio_name] = df
                    return cls._filter_date_range(df, start_date, end_date)
                except Exception:
                    pass  # Cache corrupted, will recompute

            # Compute fresh returns
            df = cls._compute_returns(portfolio_name)
            if df.empty:
                return df

            # Cache to disk
            cls._ensure_cache_dir()
            try:
                df.to_parquet(cls._get_cache_path(portfolio_name))
            except Exception as e:
                print(f"Warning: Could not cache returns for {portfolio_name}: {e}")

            # Cache in memory
            cls._memory_cache[portfolio_name] = df

            return cls._filter_date_range(df, start_date, end_date)

    @classmethod
    def _compute_returns(cls, portfolio_name: str) -> pd.DataFrame:
        """
        Compute daily returns for all tickers in a portfolio.

        Returns:
            DataFrame with daily returns for each ticker
        """
        tickers = PortfolioDataService.get_tickers(portfolio_name)
        if not tickers:
            return pd.DataFrame()

        returns_dict: Dict[str, pd.Series] = {}

        for ticker in tickers:
            try:
                # Fetch price history (uses existing cache)
                df = fetch_price_history(ticker, period="max", interval="1d")
                if df.empty:
                    continue

                # Calculate daily returns from Close prices
                close = df["Close"]
                daily_returns = close.pct_change().dropna()

                returns_dict[ticker] = daily_returns

            except Exception as e:
                print(f"Warning: Could not fetch returns for {ticker}: {e}")
                continue

        if not returns_dict:
            return pd.DataFrame()

        # Combine all returns into a single DataFrame
        # Use outer join to preserve all dates (NaN for missing)
        df = pd.DataFrame(returns_dict)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        return df

    @classmethod
    def _filter_date_range(
        cls,
        df: pd.DataFrame,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> pd.DataFrame:
        """Filter DataFrame to date range."""
        if df.empty:
            return df

        result = df.copy()

        if start_date:
            result = result[result.index >= pd.to_datetime(start_date)]

        if end_date:
            result = result[result.index <= pd.to_datetime(end_date)]

        return result

    @classmethod
    def get_portfolio_returns(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> pd.Series:
        """
        Get weighted portfolio daily returns.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter
            end_date: Optional end date filter
            weights: Optional dict of ticker -> weight.
                    If not provided, uses equal weights.

        Returns:
            Series of daily portfolio returns
        """
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        if returns.empty:
            return pd.Series(dtype=float)

        tickers = returns.columns.tolist()

        if weights is None:
            # Equal weight
            w = {t: 1.0 / len(tickers) for t in tickers}
        else:
            # Normalize weights to sum to 1
            total = sum(weights.get(t, 0) for t in tickers)
            if total == 0:
                return pd.Series(dtype=float)
            w = {t: weights.get(t, 0) / total for t in tickers}

        # Calculate weighted returns
        # Fill NaN with 0 for days where ticker didn't trade
        portfolio_returns = pd.Series(0.0, index=returns.index)
        for ticker in tickers:
            if ticker in w and w[ticker] > 0:
                ticker_returns = returns[ticker].fillna(0)
                portfolio_returns += ticker_returns * w[ticker]

        return portfolio_returns

    @classmethod
    def get_cumulative_returns(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get cumulative returns for all tickers.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with cumulative returns (1.0 = 100% gain)
        """
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        if returns.empty:
            return pd.DataFrame()

        # Calculate cumulative returns: (1 + r1) * (1 + r2) * ... - 1
        cumulative = (1 + returns).cumprod() - 1
        return cumulative

    @classmethod
    def invalidate_cache(cls, portfolio_name: str) -> None:
        """
        Invalidate cache for a portfolio.

        Call this when a portfolio is modified.

        Args:
            portfolio_name: Name of the portfolio
        """
        with cls._cache_lock:
            # Clear memory cache
            cls._memory_cache.pop(portfolio_name, None)

            # Delete disk cache
            cache_path = cls._get_cache_path(portfolio_name)
            if cache_path.exists():
                try:
                    cache_path.unlink()
                except OSError:
                    pass

    @classmethod
    def invalidate_all_caches(cls) -> None:
        """Clear all cached returns."""
        with cls._cache_lock:
            cls._memory_cache.clear()

            if cls._CACHE_DIR.exists():
                for cache_file in cls._CACHE_DIR.glob("*_returns.parquet"):
                    try:
                        cache_file.unlink()
                    except OSError:
                        pass

    @classmethod
    def get_correlation_matrix(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get correlation matrix of daily returns.

        Useful for risk analysis and diversification assessment.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Correlation matrix DataFrame
        """
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        if returns.empty:
            return pd.DataFrame()

        return returns.corr()

    @classmethod
    def get_volatility(
        cls,
        portfolio_name: str,
        window: int = 252,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get annualized rolling volatility for each ticker.

        Args:
            portfolio_name: Name of the portfolio
            window: Rolling window in days (default 252 = 1 year)
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with rolling annualized volatility
        """
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        if returns.empty:
            return pd.DataFrame()

        # Annualized volatility = daily_std * sqrt(252)
        import numpy as np

        volatility = returns.rolling(window=window).std() * np.sqrt(252)
        return volatility.dropna()
