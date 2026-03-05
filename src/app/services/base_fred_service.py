"""Base FRED Service - Shared cache/fetch infrastructure for all FRED data services."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.fred_api_key_service import FredApiKeyService

if TYPE_CHECKING:
    import pandas as pd

CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"


class BaseFredService:
    """
    Base class for FRED data services.

    Provides shared cache/fetch infrastructure:
    - Parquet disk caching with freshness checks
    - Incremental update pattern (fetch only new data since last cache)
    - ThreadPoolExecutor(10) parallel FRED API calls
    - 1-hour cooldown on failed fetches
    - YoY% computation helper

    Subclasses define series maps, cache files, and fetch_all_data() orchestration.
    """

    _FETCH_COOLDOWN = 3600  # 1-hour cooldown on failed fetches

    # ── Cache helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _is_cache_fresh(last_date, max_age_days: int) -> bool:
        from datetime import date, timedelta
        return last_date >= (date.today() - timedelta(days=max_age_days))

    @classmethod
    def _load_cache(
        cls, cache_file: Path, series_map: Dict[str, str]
    ) -> "Optional[pd.DataFrame]":
        import pandas as pd

        if not cache_file.exists():
            return None
        try:
            df = pd.read_parquet(cache_file)
            if df.empty:
                return None
            valid_cols = [c for c in df.columns if c in series_map]
            return df[valid_cols] if valid_cols else None
        except Exception:
            return None

    @classmethod
    def _save_cache(cls, df: "pd.DataFrame", cache_file: Path) -> None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(cache_file)
        except Exception:
            pass

    # ── Generic group getter with cache-with-cooldown ─────────────────────

    @classmethod
    def _get_group(
        cls,
        series_map: Dict[str, str],
        cache_file: Path,
        fetch_attr: str,
        max_age_days: int = 45,
    ) -> "Optional[pd.DataFrame]":
        """Generic cache-with-incremental-update pattern for a group of series."""
        import time

        cached = cls._load_cache(cache_file, series_map)
        if cached is not None:
            last_date = cached.index.max().date()
            if cls._is_cache_fresh(last_date, max_age_days):
                return cached

            last_fetch = getattr(cls, fetch_attr, None)
            if last_fetch is not None:
                elapsed = time.monotonic() - last_fetch
                if elapsed < cls._FETCH_COOLDOWN:
                    return cached

            setattr(cls, fetch_attr, time.monotonic())
            updated = cls._fetch_incremental(cached, series_map, cache_file)
            if updated is not None:
                return updated

        return cls._fetch_full(series_map, cache_file)

    # ── FRED fetch helpers ────────────────────────────────────────────────

    @classmethod
    def _fetch_full(
        cls, series_map: Dict[str, str], cache_file: Path
    ) -> "Optional[pd.DataFrame]":
        """Fetch full history for a group of series from FRED."""
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

            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {
                    pool.submit(_fetch_one, label, sid): label
                    for label, sid in series_map.items()
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

            cls._save_cache(df, cache_file)
            return df

        except Exception:
            return None

    @classmethod
    def _fetch_incremental(
        cls,
        cached: "pd.DataFrame",
        series_map: Dict[str, str],
        cache_file: Path,
    ) -> "Optional[pd.DataFrame]":
        """Fetch only new data since last cached date, then merge."""
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

            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {
                    pool.submit(_fetch_one, label, sid): label
                    for label, sid in series_map.items()
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

            cls._save_cache(combined, cache_file)
            return combined

        except Exception:
            return cached

    # ── Transform helpers ─────────────────────────────────────────────────

    @staticmethod
    def _compute_yoy(raw_df: "pd.DataFrame") -> "pd.DataFrame":
        """Compute year-over-year % change (periods=12) for all columns."""
        import pandas as pd

        if raw_df is None or raw_df.empty:
            return pd.DataFrame()
        result = raw_df.pct_change(periods=12) * 100
        return result.dropna(how="all")
