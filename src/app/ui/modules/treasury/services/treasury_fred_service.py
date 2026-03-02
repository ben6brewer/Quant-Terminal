"""Treasury FRED Service - Fetches US Treasury yield data from FRED API with parquet caching."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from app.services.fred_api_key_service import FredApiKeyService

if TYPE_CHECKING:
    from datetime import date
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

# Additional series
EXTRA_SERIES: Dict[str, str] = {
    "Fed Funds": "FEDFUNDS",
    "10Y-2Y Spread": "T10Y2Y",
}

# All series combined
ALL_SERIES: Dict[str, str] = {**TENOR_SERIES, **EXTRA_SERIES}

# Ordered tenor labels (for yield curve x-axis)
TENOR_LABELS: List[str] = list(TENOR_SERIES.keys())

# Numeric year values for each tenor (used for curve x-axis positioning)
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

# Default maturities to show on time series chart
DEFAULT_RATE_SERIES: List[str] = ["2Y", "5Y", "10Y", "30Y"]

# Cache path
CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
CACHE_FILE = CACHE_DIR / "treasury_data.parquet"


class TreasuryFredService:
    """
    Fetches US Treasury yield data from FRED API.

    Caches raw yield data as parquet. Treasury yields are published daily
    on trading days, so cache is considered fresh if last date >= (today - 3 days).
    """

    _last_fetch_time: Optional[float] = None
    _FETCH_COOLDOWN = 3600  # 1 hour cooldown on failed fetches

    @classmethod
    def fetch_all_treasury_data(cls) -> "Optional[pd.DataFrame]":
        """
        Fetch all treasury series, using cache when current.

        Returns:
            DataFrame with DatetimeIndex and columns for each series.
            Values are yield percentages (e.g., 4.25 = 4.25%).
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
    def get_latest_yields(cls, df: "pd.DataFrame") -> Optional[Dict]:
        """
        Get the most recent yield readings.

        Returns:
            {"10y": 4.25, "2y": 3.80, "spread": 0.45, "date": "Feb 2026"} or None
        """
        if df is None or df.empty:
            return None

        # Get last row with valid 10Y data
        if "10Y" not in df.columns:
            return None

        last_valid = df.dropna(subset=["10Y"]).iloc[-1:]
        if last_valid.empty:
            return None

        row = last_valid.iloc[0]
        dt = last_valid.index[0]

        result = {"date": dt.strftime("%b %Y")}

        if "10Y" in row.index:
            result["10y"] = round(float(row["10Y"]), 2)
        if "2Y" in row.index:
            result["2y"] = round(float(row["2Y"]), 2)
        if "10Y-2Y Spread" in row.index:
            import numpy as np
            val = row["10Y-2Y Spread"]
            if not np.isnan(val):
                result["spread"] = round(float(val), 2)

        return result

    @classmethod
    def get_yields_for_date(
        cls, df: "pd.DataFrame", target_date: "date"
    ) -> "Optional[Dict[str, float]]":
        """
        Get tenor yield values for the nearest available date.

        Returns:
            Dict mapping tenor labels to yield values, or None if unavailable
        """
        import pandas as pd

        if df is None or df.empty:
            return None

        target = pd.Timestamp(target_date)
        idx = df.index.get_indexer([target], method="ffill")
        if idx[0] == -1:
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

        if df is None or df.empty:
            return None

        target = pd.Timestamp(target_date)
        idx = df.index.get_indexer([target], method="ffill")
        if idx[0] == -1:
            idx = df.index.get_indexer([target], method="bfill")
            if idx[0] == -1:
                return None

        return df.index[idx[0]].date()

    @classmethod
    def _is_cache_fresh(cls, last_date: "date") -> bool:
        """Check if cached data is fresh enough (within 3 days)."""
        from datetime import date, timedelta
        return last_date >= (date.today() - timedelta(days=3))

    @classmethod
    def _load_cache(cls) -> "Optional[pd.DataFrame]":
        """Load cached treasury data from parquet."""
        import pandas as pd

        if not CACHE_FILE.exists():
            return None
        try:
            df = pd.read_parquet(CACHE_FILE)
            if df.empty:
                return None
            valid_cols = [c for c in df.columns if c in ALL_SERIES]
            if not valid_cols:
                return None
            return df[valid_cols]
        except Exception:
            return None

    @classmethod
    def _save_cache(cls, df: "pd.DataFrame") -> None:
        """Save treasury data to parquet cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(CACHE_FILE)
        except Exception:
            pass

    @classmethod
    def _fetch_full(cls) -> "Optional[pd.DataFrame]":
        """Fetch full history for all treasury series from FRED."""
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

            with ThreadPoolExecutor(max_workers=13) as pool:
                futures = {
                    pool.submit(_fetch_one, label, sid): label
                    for label, sid in ALL_SERIES.items()
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

            with ThreadPoolExecutor(max_workers=13) as pool:
                futures = {
                    pool.submit(_fetch_one, label, sid): label
                    for label, sid in ALL_SERIES.items()
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
