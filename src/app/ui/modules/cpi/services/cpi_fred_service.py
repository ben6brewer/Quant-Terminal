"""CPI FRED Service - Fetches CPI data from FRED API with parquet caching."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.fred_api_key_service import FredApiKeyService

if TYPE_CHECKING:
    import pandas as pd

# FRED series IDs for CPI data (all index-type, need YoY% calculation)
CPI_INDEX_SERIES: Dict[str, str] = {
    "Headline CPI": "CPIAUCSL",
    "Food & Beverages": "CPIFABSL",
    "Energy": "CPIENGSL",
    "Housing": "CPIHOSSL",
    "Transportation": "CPITRNSL",
    "Medical Care": "CPIMEDSL",
    "Apparel": "CPIAPPSL",
    "Education": "CPIEDUSL",
    "Recreation": "CPIRECSL",
}

# Component series (the 8 sub-categories)
COMPONENT_LABELS = [
    "Food & Beverages", "Energy", "Housing", "Transportation",
    "Medical Care", "Apparel", "Education", "Recreation",
]

# Approximate BLS relative importance weights (sum ~0.972).
# Raw weighted contributions are normalized to headline each month,
# so exact values only control relative segment proportions.
COMPONENT_WEIGHTS = {
    "Food & Beverages": 0.143,
    "Energy": 0.070,
    "Housing": 0.404,
    "Transportation": 0.131,
    "Medical Care": 0.084,
    "Apparel": 0.025,
    "Education": 0.060,
    "Recreation": 0.055,
}

# Cache path
CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
CACHE_FILE = CACHE_DIR / "cpi_data.parquet"


class CpiFredService:
    """
    Fetches CPI data from FRED API.

    Caches raw index data as parquet. CPI is published monthly with ~2 week lag,
    so cache is considered fresh if last date >= (today - 45 days).
    """

    _last_fetch_time: Optional[float] = None
    _FETCH_COOLDOWN = 3600  # 1 hour cooldown on failed fetches

    @classmethod
    def fetch_all_cpi_data(cls) -> "Optional[pd.DataFrame]":
        """
        Fetch all CPI series, using cache when current.

        Returns:
            DataFrame with DatetimeIndex and columns for each CPI series.
            Columns contain raw index values.
            Returns None if API key missing or fetch fails.
        """
        import pandas as pd

        cached = cls._load_cache()
        if cached is not None:
            last_date = cached.index.max().date()
            if cls._is_cache_fresh(last_date):
                return cached

            import time
            if cls._last_fetch_time is not None:
                elapsed = time.monotonic() - cls._last_fetch_time
                if elapsed < cls._FETCH_COOLDOWN:
                    return cached

            cls._last_fetch_time = time.monotonic()
            updated = cls._fetch_incremental(cached)
            if updated is not None:
                return updated

        return cls._fetch_full()

    @classmethod
    def compute_yoy_pct(cls, raw_df: "pd.DataFrame") -> "pd.DataFrame":
        """
        Compute Year-over-Year % change for all series.

        Returns:
            DataFrame with all columns in YoY% terms.
        """
        import pandas as pd

        if raw_df is None or raw_df.empty:
            return pd.DataFrame()

        result = raw_df.pct_change(periods=12) * 100
        return result.dropna(how="all")

    @classmethod
    def get_latest_reading(cls, yoy_df: "pd.DataFrame") -> Optional[Dict]:
        """
        Get the most recent headline CPI reading.

        Returns:
            {"headline": 3.2, "date": "Jan 2026"} or None
        """
        if yoy_df is None or yoy_df.empty:
            return None

        last_valid = yoy_df.dropna(subset=["Headline CPI"]).iloc[-1:]
        if last_valid.empty:
            return None

        row = last_valid.iloc[0]
        dt = last_valid.index[0]
        return {
            "headline": round(float(row["Headline CPI"]), 1),
            "date": dt.strftime("%b %Y"),
        }

    @classmethod
    def _is_cache_fresh(cls, last_date) -> bool:
        """Check if cached data is fresh enough (within 45 days)."""
        from datetime import date, timedelta
        return last_date >= (date.today() - timedelta(days=45))

    @classmethod
    def _load_cache(cls) -> "Optional[pd.DataFrame]":
        """Load cached CPI data from parquet."""
        import pandas as pd

        if not CACHE_FILE.exists():
            return None
        try:
            df = pd.read_parquet(CACHE_FILE)
            if df.empty:
                return None
            # Drop columns that are no longer in our series set
            valid_cols = [c for c in df.columns if c in CPI_INDEX_SERIES]
            if not valid_cols:
                return None
            return df[valid_cols]
        except Exception:
            return None

    @classmethod
    def _save_cache(cls, df: "pd.DataFrame") -> None:
        """Save CPI data to parquet cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(CACHE_FILE)
        except Exception:
            pass

    @classmethod
    def _fetch_full(cls) -> "Optional[pd.DataFrame]":
        """Fetch full history for all CPI series from FRED."""
        import pandas as pd
        from concurrent.futures import ThreadPoolExecutor, as_completed

        api_key = FredApiKeyService.get_api_key()
        if not api_key:
            return None

        try:
            from fredapi import Fred
            fred = Fred(api_key=api_key)
            frames = {}

            def _fetch_one(label, series_id):
                data = fred.get_series(series_id)
                return label, data

            with ThreadPoolExecutor(max_workers=9) as pool:
                futures = {
                    pool.submit(_fetch_one, label, sid): label
                    for label, sid in CPI_INDEX_SERIES.items()
                }
                for future in as_completed(futures):
                    try:
                        label, data = future.result()
                        if data is not None and not data.empty:
                            frames[label] = data
                    except Exception:
                        continue

            if not frames:
                return None

            df = pd.DataFrame(frames)
            df.index.name = "Date"
            df = df.ffill()
            df = df.dropna(how="all")

            cls._save_cache(df)
            return df

        except Exception:
            return None

    @classmethod
    def _fetch_incremental(cls, cached: "pd.DataFrame") -> "Optional[pd.DataFrame]":
        """Fetch only new data since last cached date, merge with cache."""
        import pandas as pd
        from concurrent.futures import ThreadPoolExecutor, as_completed

        api_key = FredApiKeyService.get_api_key()
        if not api_key:
            return None

        try:
            from fredapi import Fred
            fred = Fred(api_key=api_key)

            last_date = cached.index.max()
            start_date = last_date.strftime("%Y-%m-%d")
            frames = {}

            def _fetch_one(label, series_id):
                data = fred.get_series(series_id, observation_start=start_date)
                return label, data

            with ThreadPoolExecutor(max_workers=9) as pool:
                futures = {
                    pool.submit(_fetch_one, label, sid): label
                    for label, sid in CPI_INDEX_SERIES.items()
                }
                for future in as_completed(futures):
                    try:
                        label, data = future.result()
                        if data is not None and not data.empty:
                            frames[label] = data
                    except Exception:
                        continue

            if not frames:
                return cached

            new_data = pd.DataFrame(frames)
            new_data.index.name = "Date"

            combined = pd.concat([cached, new_data])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
            combined = combined.ffill()

            cls._save_cache(combined)
            new_last_date = combined.index.max()
            if new_last_date > last_date:
                cls._last_fetch_time = None
            return combined

        except Exception:
            return cached
