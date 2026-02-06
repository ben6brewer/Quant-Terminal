"""FMP Holdings Service - Fetches historical ETF holdings from Financial Modeling Prep.

Provides weekly snapshots of ETF constituent weights for time-varying
benchmark attribution in Risk Analytics.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    import pandas as pd


class FMPHoldingsService:
    """
    Fetches historical ETF holdings from Financial Modeling Prep API.

    Provides weekly snapshots of ETF constituent weights for
    time-varying benchmark attribution.
    """

    # API Endpoints
    BASE_URL = "https://financialmodelingprep.com/api/v4"
    HOLDINGS_DATES_ENDPOINT = "/etf-holdings/portfolio-date"
    HOLDINGS_ENDPOINT = "/etf-holdings"

    # Cache settings
    CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fmp_holdings"

    # Class-level API key cache
    _api_key: Optional[str] = None

    @classmethod
    def get_historical_weights(
        cls,
        etf_symbol: str,
        start_date: str,
        end_date: str,
    ) -> "pd.DataFrame":
        """
        Get weekly ETF weights for date range, interpolated to daily.

        Args:
            etf_symbol: ETF ticker symbol (e.g., "IWV")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with DatetimeIndex and ticker columns,
            values are weights (decimals summing to ~1.0).
            Returns empty DataFrame if FMP unavailable.
        """
        import pandas as pd

        # Check for API key
        api_key = cls._load_api_key()
        if not api_key:
            print("[FMP] No API key found, returning empty DataFrame")
            return pd.DataFrame()

        # Get available dates from FMP
        available_dates = cls.get_available_dates(etf_symbol)
        if not available_dates:
            print(f"[FMP] No available dates for {etf_symbol}")
            return pd.DataFrame()

        # Select weekly dates within range
        weekly_dates = cls._select_weekly_dates(available_dates, start_date, end_date)
        if not weekly_dates:
            print(f"[FMP] No weekly dates found in range {start_date} to {end_date}")
            return pd.DataFrame()

        print(f"[FMP] Fetching {len(weekly_dates)} weekly snapshots for {etf_symbol}")

        # Fetch holdings for each weekly date
        weekly_snapshots: Dict[str, Dict[str, float]] = {}
        for date in weekly_dates:
            holdings = cls.fetch_holdings_for_date(etf_symbol, date)
            if holdings:
                weekly_snapshots[date] = holdings

        if not weekly_snapshots:
            print(f"[FMP] Failed to fetch any holdings for {etf_symbol}")
            return pd.DataFrame()

        # Interpolate to daily weights
        daily_weights = cls._interpolate_daily_weights(
            weekly_snapshots, start_date, end_date
        )

        print(f"[FMP] Created daily weights DataFrame: {daily_weights.shape}")
        return daily_weights

    @classmethod
    def get_available_dates(cls, etf_symbol: str) -> List[str]:
        """
        Get all available holding dates from FMP for an ETF.

        Args:
            etf_symbol: ETF ticker symbol

        Returns:
            List of date strings (YYYY-MM-DD), sorted descending (newest first)
        """
        import requests

        # Check cache first
        cache_path = cls.CACHE_DIR / etf_symbol / "available_dates.json"
        cached_dates = cls._load_available_dates_cache(cache_path)
        if cached_dates is not None:
            return cached_dates

        # Fetch from API
        api_key = cls._load_api_key()
        if not api_key:
            return []

        url = f"{cls.BASE_URL}{cls.HOLDINGS_DATES_ENDPOINT}"
        params = {"symbol": etf_symbol, "apikey": api_key}

        try:
            print(f"[FMP] Fetching available dates for {etf_symbol}...")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            dates = response.json()
            if isinstance(dates, list) and dates:
                # Sort descending (newest first)
                dates = sorted(dates, reverse=True)
                # Cache the result
                cls._save_available_dates_cache(cache_path, dates)
                print(f"[FMP] Found {len(dates)} available dates for {etf_symbol}")
                return dates
            else:
                print(f"[FMP] No dates returned for {etf_symbol}")
                return []

        except requests.RequestException as e:
            print(f"[FMP] Error fetching available dates: {e}")
            return []

    @classmethod
    def fetch_holdings_for_date(
        cls,
        etf_symbol: str,
        date: str,
    ) -> Dict[str, float]:
        """
        Fetch ETF holdings for a specific date.

        Args:
            etf_symbol: ETF ticker symbol
            date: Date string (YYYY-MM-DD)

        Returns:
            Dict mapping ticker -> weight (as decimal, e.g., 0.065 for 6.5%)
        """
        import requests

        # Check cache first
        cached = cls._load_from_cache(etf_symbol, date)
        if cached is not None:
            return cached

        # Fetch from API
        api_key = cls._load_api_key()
        if not api_key:
            return {}

        url = f"{cls.BASE_URL}{cls.HOLDINGS_ENDPOINT}"
        params = {"symbol": etf_symbol, "date": date, "apikey": api_key}

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, list) or not data:
                print(f"[FMP] No holdings returned for {etf_symbol} on {date}")
                return {}

            # Parse holdings - convert weightPercentage to decimal
            holdings: Dict[str, float] = {}
            for item in data:
                ticker = item.get("asset", "")
                weight_pct = item.get("weightPercentage", 0)

                if ticker and weight_pct:
                    # Convert percentage to decimal (6.5 -> 0.065)
                    holdings[ticker] = float(weight_pct) / 100.0

            # Cache the result
            if holdings:
                cls._save_to_cache(etf_symbol, date, holdings)

            return holdings

        except requests.RequestException as e:
            print(f"[FMP] Error fetching holdings for {date}: {e}")
            return {}

    @classmethod
    def _load_api_key(cls) -> Optional[str]:
        """Load FMP_API_KEY from .env file."""
        if cls._api_key is not None:
            return cls._api_key

        from dotenv import load_dotenv

        # Load from project root .env
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        load_dotenv(env_path)

        cls._api_key = os.getenv("FMP_API_KEY")

        if not cls._api_key:
            print("[FMP] Warning: FMP_API_KEY not found in .env file")

        return cls._api_key

    @classmethod
    def _select_weekly_dates(
        cls,
        available_dates: List[str],
        start_date: str,
        end_date: str,
    ) -> List[str]:
        """
        Select ~weekly snapshots from available dates.

        Strategy: Pick one date per week, preferring Fridays.

        Args:
            available_dates: List of available dates (YYYY-MM-DD)
            start_date: Start of range
            end_date: End of range

        Returns:
            List of selected dates, sorted ascending
        """
        from datetime import datetime

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        # Filter to dates within range
        dates_in_range = []
        for date_str in available_dates:
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                if start <= date <= end:
                    dates_in_range.append(date_str)
            except ValueError:
                continue

        if not dates_in_range:
            return []

        # Sort ascending
        dates_in_range = sorted(dates_in_range)

        # Select approximately weekly dates
        # Strategy: pick first date, then next date at least 5 days later
        selected = []
        last_selected = None

        for date_str in dates_in_range:
            date = datetime.strptime(date_str, "%Y-%m-%d")

            if last_selected is None:
                selected.append(date_str)
                last_selected = date
            elif (date - last_selected).days >= 5:
                selected.append(date_str)
                last_selected = date

        return selected

    @classmethod
    def _interpolate_daily_weights(
        cls,
        weekly_snapshots: Dict[str, Dict[str, float]],
        start_date: str,
        end_date: str,
    ) -> "pd.DataFrame":
        """
        Create daily weights DataFrame from weekly snapshots.

        Strategy: Forward-fill weights until next snapshot.

        Args:
            weekly_snapshots: Dict mapping date -> {ticker -> weight}
            start_date: Start of range
            end_date: End of range

        Returns:
            DataFrame with DatetimeIndex and ticker columns
        """
        import pandas as pd

        if not weekly_snapshots:
            return pd.DataFrame()

        # Get all unique tickers across all snapshots
        all_tickers = set()
        for holdings in weekly_snapshots.values():
            all_tickers.update(holdings.keys())

        all_tickers = sorted(all_tickers)

        # Create date range
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")

        # Sort snapshot dates
        snapshot_dates = sorted(weekly_snapshots.keys())

        # Build DataFrame row by row
        data = []
        current_weights: Dict[str, float] = {}

        snapshot_idx = 0
        for date in date_range:
            date_str = date.strftime("%Y-%m-%d")

            # Check if we should use a new snapshot
            while (
                snapshot_idx < len(snapshot_dates)
                and snapshot_dates[snapshot_idx] <= date_str
            ):
                current_weights = weekly_snapshots[snapshot_dates[snapshot_idx]]
                snapshot_idx += 1

            # Use current weights (forward-filled)
            if current_weights:
                row = {ticker: current_weights.get(ticker, 0.0) for ticker in all_tickers}
                data.append(row)
            else:
                # No snapshot yet, use zeros
                data.append({ticker: 0.0 for ticker in all_tickers})

        # Create DataFrame
        df = pd.DataFrame(data, index=date_range)

        # Filter to only trading days (weekdays)
        df = df[df.index.dayofweek < 5]

        return df

    @classmethod
    def _get_cache_path(cls, etf_symbol: str, date: str) -> Path:
        """Get cache file path for specific date snapshot."""
        return cls.CACHE_DIR / etf_symbol / f"{date}.json"

    @classmethod
    def _load_from_cache(cls, etf_symbol: str, date: str) -> Optional[Dict[str, float]]:
        """Load cached holdings for date."""
        cache_path = cls._get_cache_path(etf_symbol, date)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    @classmethod
    def _save_to_cache(cls, etf_symbol: str, date: str, holdings: Dict[str, float]):
        """Save holdings to cache."""
        cache_path = cls._get_cache_path(etf_symbol, date)

        # Ensure directory exists
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(cache_path, "w") as f:
                json.dump(holdings, f)
        except IOError as e:
            print(f"[FMP] Error saving cache: {e}")

    @classmethod
    def _load_available_dates_cache(cls, cache_path: Path) -> Optional[List[str]]:
        """Load cached available dates if fresh (< 1 day old)."""
        if not cache_path.exists():
            return None

        # Check if cache is stale (> 1 day old)
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        if datetime.now() - mtime > timedelta(days=1):
            return None

        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    @classmethod
    def _save_available_dates_cache(cls, cache_path: Path, dates: List[str]):
        """Save available dates to cache."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(cache_path, "w") as f:
                json.dump(dates, f)
        except IOError as e:
            print(f"[FMP] Error saving available dates cache: {e}")

    @classmethod
    def clear_cache(cls, etf_symbol: Optional[str] = None):
        """
        Clear cached holdings data.

        Args:
            etf_symbol: If provided, only clear cache for this ETF.
                       If None, clear all FMP holdings cache.
        """
        import shutil

        if etf_symbol:
            cache_path = cls.CACHE_DIR / etf_symbol
            if cache_path.exists():
                shutil.rmtree(cache_path)
                print(f"[FMP] Cleared cache for {etf_symbol}")
        else:
            if cls.CACHE_DIR.exists():
                shutil.rmtree(cls.CACHE_DIR)
                print("[FMP] Cleared all FMP holdings cache")
