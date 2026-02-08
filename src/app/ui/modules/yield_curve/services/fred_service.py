"""FRED Service - Fetches US Treasury yield data from FRED API with parquet caching."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    import pandas as pd

# FRED series IDs for US Treasury yields
TENOR_SERIES: Dict[str, str] = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "3Y": "DGS3",
    "5Y": "DGS5",
    "7Y": "DGS7",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}

# Numeric year values for each tenor (used for interpolation x-axis)
TENOR_YEARS: Dict[str, float] = {
    "1M": 1 / 12,
    "3M": 0.25,
    "6M": 0.5,
    "1Y": 1.0,
    "2Y": 2.0,
    "3Y": 3.0,
    "5Y": 5.0,
    "7Y": 7.0,
    "10Y": 10.0,
    "20Y": 20.0,
    "30Y": 30.0,
}

# Ordered tenor labels
TENOR_LABELS = list(TENOR_SERIES.keys())

# Cache path
CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
CACHE_FILE = CACHE_DIR / "treasury_yields.parquet"


class FredService:
    """
    Fetches US Treasury yield data from FRED API.

    Caches data as parquet for fast reload. Follows NYSE schedule
    for cache freshness (FRED publishes on trading days).
    """

    _api_key: Optional[str] = None
    _last_fetch_time: Optional[float] = None  # monotonic timestamp of last API call
    _FETCH_COOLDOWN = 3600  # Skip refetch within 1 hour of a failed advance

    @classmethod
    def has_api_key(cls) -> bool:
        """Check if a FRED API key is available."""
        return cls._load_api_key() is not None

    @classmethod
    def set_api_key(cls, key: str) -> None:
        """Save FRED API key to .env file and update class cache."""
        env_path = Path(__file__).parent.parent.parent.parent.parent.parent.parent / ".env"

        # Read existing .env content
        lines = []
        found = False
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if line.startswith("FRED_API_KEY="):
                        lines.append(f"FRED_API_KEY={key}\n")
                        found = True
                    else:
                        lines.append(line)

        if not found:
            lines.append(f"FRED_API_KEY={key}\n")

        with open(env_path, "w") as f:
            f.writelines(lines)

        cls._api_key = key

    @classmethod
    def _load_api_key(cls) -> Optional[str]:
        """Load FRED_API_KEY from .env file (cached)."""
        if cls._api_key is not None:
            return cls._api_key

        from dotenv import load_dotenv

        env_path = Path(__file__).parent.parent.parent.parent.parent.parent.parent / ".env"
        load_dotenv(env_path)

        cls._api_key = os.getenv("FRED_API_KEY") or None

        return cls._api_key

    @classmethod
    def fetch_all_yields(cls) -> "pd.DataFrame":
        """
        Fetch all treasury yield data, using cache when current.

        Returns:
            DataFrame with DatetimeIndex and columns for each tenor (1M, 3M, ..., 30Y).
            Values are yield percentages (e.g., 4.25 = 4.25%).
            Returns empty DataFrame if API key missing or fetch fails.
        """
        import pandas as pd

        # Try loading from cache first
        cached = cls._load_cache()
        if cached is not None:
            from app.utils.market_hours import is_stock_cache_current

            last_date = cached.index.max().date()
            if is_stock_cache_current(last_date):
                print("[FRED] Cache is current, using cached data")
                return cached

            # Skip refetch if we already tried recently (FRED has ~1 day pub lag)
            import time

            if cls._last_fetch_time is not None:
                elapsed = time.monotonic() - cls._last_fetch_time
                if elapsed < cls._FETCH_COOLDOWN:
                    print("[FRED] Cache checked recently, using cached data")
                    return cached

            # Cache exists but stale - do incremental update
            print(f"[FRED] Cache stale (last: {last_date}), fetching updates...")
            cls._last_fetch_time = time.monotonic()
            updated = cls._fetch_incremental(cached)
            if updated is not None:
                return updated

        # No cache or incremental failed - full fetch
        print("[FRED] Performing full fetch...")
        return cls._fetch_full()

    @classmethod
    def _load_cache(cls) -> "Optional[pd.DataFrame]":
        """Load cached yield data from parquet."""
        import pandas as pd

        if not CACHE_FILE.exists():
            return None

        try:
            df = pd.read_parquet(CACHE_FILE)
            if df.empty:
                return None
            return df
        except Exception as e:
            print(f"[FRED] Cache read error: {e}")
            return None

    @classmethod
    def _save_cache(cls, df: "pd.DataFrame") -> None:
        """Save yield data to parquet cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(CACHE_FILE)
            print(f"[FRED] Saved cache ({len(df)} rows)")
        except Exception as e:
            print(f"[FRED] Cache write error: {e}")

    @classmethod
    def _fetch_full(cls) -> "pd.DataFrame":
        """Fetch full history for all tenor series from FRED."""
        import pandas as pd

        api_key = cls._load_api_key()
        if not api_key:
            return pd.DataFrame()

        try:
            from fredapi import Fred

            fred = Fred(api_key=api_key)
            frames = {}

            for tenor, series_id in TENOR_SERIES.items():
                try:
                    data = fred.get_series(series_id)
                    if data is not None and not data.empty:
                        frames[tenor] = data
                except Exception as e:
                    print(f"[FRED] Error fetching {series_id}: {e}")

            if not frames:
                print("[FRED] No data fetched from any series")
                return pd.DataFrame()

            df = pd.DataFrame(frames)
            df.index.name = "Date"
            df = df.ffill()  # Forward-fill missing values
            df = df.dropna(how="all")

            cls._save_cache(df)
            print(f"[FRED] Full fetch complete: {len(df)} rows, {len(df.columns)} tenors")
            return df

        except Exception as e:
            print(f"[FRED] Full fetch error: {e}")
            return pd.DataFrame()

    @classmethod
    def _fetch_incremental(cls, cached: "pd.DataFrame") -> "Optional[pd.DataFrame]":
        """Fetch only new data since last cached date, merge with cache."""
        import pandas as pd

        api_key = cls._load_api_key()
        if not api_key:
            return None

        try:
            from fredapi import Fred

            fred = Fred(api_key=api_key)

            last_date = cached.index.max()
            start_date = last_date.strftime("%Y-%m-%d")
            frames = {}

            for tenor, series_id in TENOR_SERIES.items():
                try:
                    data = fred.get_series(series_id, observation_start=start_date)
                    if data is not None and not data.empty:
                        frames[tenor] = data
                except Exception as e:
                    print(f"[FRED] Incremental error for {series_id}: {e}")

            if not frames:
                return cached

            new_data = pd.DataFrame(frames)
            new_data.index.name = "Date"

            # Merge: new data overwrites overlapping dates
            combined = pd.concat([cached, new_data])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
            combined = combined.ffill()

            cls._save_cache(combined)
            new_last_date = combined.index.max()
            advanced = new_last_date > last_date
            if advanced:
                # New data found — clear cooldown so next expected date isn't blocked
                cls._last_fetch_time = None
            print(f"[FRED] Incremental update: {len(new_data)} new rows, {len(combined)} total"
                  f"{'' if advanced else ' (no new dates)'}")
            return combined

        except Exception as e:
            print(f"[FRED] Incremental fetch error: {e}")
            return cached

    @classmethod
    def get_yields_for_date(
        cls, df: "pd.DataFrame", target_date: "date"
    ) -> "Optional[Dict[str, float]]":
        """
        Get yield values for the nearest available date.

        Args:
            df: Full yield DataFrame
            target_date: Target date to look up

        Returns:
            Dict mapping tenor labels to yield values, or None if unavailable
        """
        import pandas as pd

        if df.empty:
            return None

        target = pd.Timestamp(target_date)

        # Find nearest date (prefer exact or earlier)
        idx = df.index.get_indexer([target], method="ffill")
        if idx[0] == -1:
            # target_date is before the earliest data
            idx = df.index.get_indexer([target], method="bfill")
            if idx[0] == -1:
                return None

        row = df.iloc[idx[0]]
        result = {}
        for tenor in TENOR_LABELS:
            if tenor in row.index and pd.notna(row[tenor]):
                result[tenor] = float(row[tenor])

        return result if result else None

    @classmethod
    def get_actual_date(cls, df: "pd.DataFrame", target_date: "date") -> "Optional[date]":
        """Get the actual date used for a target date lookup (nearest available)."""
        import pandas as pd

        if df.empty:
            return None

        target = pd.Timestamp(target_date)
        idx = df.index.get_indexer([target], method="ffill")
        if idx[0] == -1:
            idx = df.index.get_indexer([target], method="bfill")
            if idx[0] == -1:
                return None

        return df.index[idx[0]].date()
