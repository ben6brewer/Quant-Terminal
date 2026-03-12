"""Base FRED Service - Shared cache/fetch infrastructure for all FRED data services."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.fred_api_key_service import FredApiKeyService

if TYPE_CHECKING:
    import pandas as pd

CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"

_FRED_CACHE_VERSION = "2"
_FRED_VERSION_FILE = CACHE_DIR / ".fred_cache_version"

_version_checked = False


def _check_fred_cache_version():
    """One-time wipe of FRED caches when version changes."""
    global _version_checked
    if _version_checked:
        return
    if _FRED_VERSION_FILE.exists():
        if _FRED_VERSION_FILE.read_text().strip() == _FRED_CACHE_VERSION:
            _version_checked = True
            return
    # Version mismatch or no version file — delete all parquet files
    if CACHE_DIR.exists():
        deleted = list(CACHE_DIR.glob("*.parquet"))
        for f in deleted:
            f.unlink(missing_ok=True)
        if deleted:
            logging.info(
                "FRED cache version bump to v%s — deleted %d parquet files",
                _FRED_CACHE_VERSION,
                len(deleted),
            )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _FRED_VERSION_FILE.write_text(_FRED_CACHE_VERSION)
    _version_checked = True


class BaseFredService:
    """
    Base class for FRED data services.

    Provides shared cache/fetch infrastructure:
    - Parquet disk caching with freshness checks
    - Incremental update pattern (fetch only new data since last cache)
    - ThreadPoolExecutor(10) parallel FRED API calls
    - 1-hour cooldown on failed fetches
    - YoY% computation helper
    - Declarative GROUPS config for auto-generated fetch_all_data()

    Subclasses either:
    1. Define GROUPS list for auto-generated fetch_all_data(), or
    2. Override fetch_all_data() for custom orchestration.
    """

    GROUPS = []  # List[FredGroup] — subclasses declare for auto-generated fetch_all_data
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
            if not valid_cols:
                return None
            return df[valid_cols]
        except Exception:
            logging.warning("Failed to read FRED cache %s — deleting", cache_file.name)
            cache_file.unlink(missing_ok=True)
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

        _check_fred_cache_version()

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
            logging.warning("No FRED API key — cannot fetch %s", cache_file.name)
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
                        logging.exception("FRED fetch failed for series %s", futures[future])

            if not frames:
                return None

            df = pd.DataFrame(frames)
            df.index.name = "Date"
            df = df.ffill()
            df = df.dropna(how="all")

            cls._save_cache(df, cache_file)
            return df

        except Exception:
            logging.exception("FRED full fetch failed for %s", cache_file.name)
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
            logging.warning("No FRED API key — cannot fetch %s", cache_file.name)
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
                        logging.exception("FRED incremental fetch failed for series %s", futures[future])

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
            logging.exception("FRED incremental fetch failed for %s", cache_file.name)
            return cached

    # ── Declarative GROUPS → auto-generated fetch_all_data ───────────────

    @classmethod
    def fetch_all_data(cls) -> "Optional[Dict[str, pd.DataFrame]]":
        """Auto-generated from GROUPS. Override for custom logic."""
        if not cls.GROUPS:
            raise NotImplementedError(
                f"{cls.__name__} must define GROUPS or override fetch_all_data()"
            )
        result = {}
        for i, group in enumerate(cls.GROUPS):
            cache_path = CACHE_DIR / group.cache_file
            fetch_attr = f"_last_group_{i}_fetch"
            raw = cls._get_group(
                group.series, cache_path, fetch_attr, group.max_age_days
            )
            if raw is None or raw.empty:
                continue
            for output in group.outputs:
                cols = [c for c in output.columns if c in raw.columns]
                if not cols:
                    continue
                df = raw[cols].dropna(how="all").copy()
                if output.unit_scale is not None:
                    df = df * output.unit_scale
                result[output.key] = df
        if not result:
            return None
        cls._data = result
        return result

    # ── Stats helper ──────────────────────────────────────────────────────

    @staticmethod
    def _latest_value(data, data_key, col, decimals=2):
        """Extract latest non-NaN value from data[data_key][col]."""
        df = data.get(data_key)
        if df is None or col not in df.columns:
            return None
        s = df[col].dropna()
        return round(float(s.iloc[-1]), decimals) if not s.empty else None

    # ── Transform helpers ─────────────────────────────────────────────────

    @staticmethod
    def _compute_yoy(raw_df: "pd.DataFrame") -> "pd.DataFrame":
        """Compute year-over-year % change (periods=12) for all columns."""
        import pandas as pd

        if raw_df is None or raw_df.empty:
            return pd.DataFrame()
        result = raw_df.pct_change(periods=12) * 100
        return result.dropna(how="all")
