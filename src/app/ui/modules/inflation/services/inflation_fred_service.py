"""Inflation FRED Service - Fetches CPI, PCE, PPI, and expectations data from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.fred_api_key_service import FredApiKeyService

if TYPE_CHECKING:
    import pandas as pd

# ─── Series definitions ───────────────────────────────────────────────────────

CPI_SERIES: Dict[str, str] = {
    "Headline CPI": "CPIAUCSL",
    "Core CPI":     "CPILFESL",
    "Food & Beverages": "CPIFABSL",
    "Energy":       "CPIENGSL",
    "Housing":      "CPIHOSSL",
    "Transportation": "CPITRNSL",
    "Medical Care": "CPIMEDSL",
    "Apparel":      "CPIAPPSL",
    "Education":    "CPIEDUSL",
    "Recreation":   "CPIRECSL",
}

PCE_SERIES: Dict[str, str] = {
    "PCE":      "PCEPI",
    "Core PCE": "PCEPILFE",
}

PPI_SERIES: Dict[str, str] = {
    "PPI Final Demand": "PPIFID",
    "PPI Core":         "PPICOR",
    "PPI Energy":       "PPIDES",
    "PPI Services":     "PPIFDS",
}

# Breakevens are already in % (market-implied), Michigan is already in %
EXPECTATIONS_SERIES: Dict[str, str] = {
    "5Y Breakeven":  "T5YIEM",
    "10Y Breakeven": "T10YIEM",
    "Michigan 1Y":   "MICH",
}

# Cache paths
CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
CPI_CACHE_FILE         = CACHE_DIR / "cpi_data.parquet"           # backward-compatible name
PCE_CACHE_FILE         = CACHE_DIR / "pce_data.parquet"
PPI_CACHE_FILE         = CACHE_DIR / "ppi_data.parquet"
EXPECTATIONS_CACHE_FILE = CACHE_DIR / "inflation_expectations_data.parquet"


class InflationFredService:
    """
    Fetches all inflation data (CPI, PCE, PPI, Expectations) from FRED.

    Class-level cache: once fetched, subsequent callers in the same session
    return instantly without hitting FRED again.

    Monthly series (CPI, PCE, PPI) — cache freshness: 45 days.
    Expectations (monthly breakevens + Michigan) — cache freshness: 7 days.
    """

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_cpi_fetch: Optional[float] = None
    _last_pce_fetch: Optional[float] = None
    _last_ppi_fetch: Optional[float] = None
    _last_exp_fetch: Optional[float] = None
    _FETCH_COOLDOWN = 3600  # 1-hour cooldown on failed fetches

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        """
        Fetch all inflation data, using cache when current.

        Returns:
            Dict with keys:
              "cpi"          - DataFrame (YoY %) with Headline CPI, Core CPI, 8 components
              "pce"          - DataFrame (YoY %) with PCE, Core PCE
              "ppi"          - DataFrame (YoY %) with 4 PPI series
              "expectations" - DataFrame (already %) with 5Y Breakeven, 10Y Breakeven, Michigan 1Y
            Returns None if API key missing or all fetches fail.
        """
        import pandas as pd

        cpi_raw  = cls._get_cpi_raw()
        pce_raw  = cls._get_pce_raw()
        ppi_raw  = cls._get_ppi_raw()
        exp_df   = cls._get_expectations()

        result: Dict[str, pd.DataFrame] = {}

        if cpi_raw is not None and not cpi_raw.empty:
            result["cpi"] = cls._compute_yoy(cpi_raw)

        if pce_raw is not None and not pce_raw.empty:
            result["pce"] = cls._compute_yoy(pce_raw)

        if ppi_raw is not None and not ppi_raw.empty:
            result["ppi"] = cls._compute_yoy(ppi_raw)

        if exp_df is not None and not exp_df.empty:
            result["expectations"] = exp_df

        if not result:
            return None

        cls._data = result
        return result

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        """
        Extract the most recent readings for CPI Overview stat cards.

        Returns dict with: headline_cpi, core_cpi, pce, core_pce, date
        """
        if not data:
            return None

        result = {}

        cpi_df = data.get("cpi")
        if cpi_df is not None and not cpi_df.empty:
            if "Headline CPI" in cpi_df.columns:
                s = cpi_df["Headline CPI"].dropna()
                if not s.empty:
                    result["headline_cpi"] = round(float(s.iloc[-1]), 2)
                    result["date"] = s.index[-1].strftime("%b %Y")
            if "Core CPI" in cpi_df.columns:
                s = cpi_df["Core CPI"].dropna()
                if not s.empty:
                    result["core_cpi"] = round(float(s.iloc[-1]), 2)

        pce_df = data.get("pce")
        if pce_df is not None and not pce_df.empty:
            if "PCE" in pce_df.columns:
                s = pce_df["PCE"].dropna()
                if not s.empty:
                    result["pce"] = round(float(s.iloc[-1]), 2)
            if "Core PCE" in pce_df.columns:
                s = pce_df["Core PCE"].dropna()
                if not s.empty:
                    result["core_pce"] = round(float(s.iloc[-1]), 2)

        return result if result else None

    # ──────────────────────────────────────────────────────────────────────────
    # YoY% computation
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _compute_yoy(cls, raw_df: "pd.DataFrame") -> "pd.DataFrame":
        """Compute year-over-year % change (periods=12) for all columns."""
        import pandas as pd

        if raw_df is None or raw_df.empty:
            return pd.DataFrame()
        result = raw_df.pct_change(periods=12) * 100
        return result.dropna(how="all")

    # ──────────────────────────────────────────────────────────────────────────
    # Per-group raw data getters (with cache logic)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _get_cpi_raw(cls) -> "Optional[pd.DataFrame]":
        return cls._get_monthly_group(
            CPI_SERIES, CPI_CACHE_FILE, "_last_cpi_fetch"
        )

    @classmethod
    def _get_pce_raw(cls) -> "Optional[pd.DataFrame]":
        return cls._get_monthly_group(
            PCE_SERIES, PCE_CACHE_FILE, "_last_pce_fetch"
        )

    @classmethod
    def _get_ppi_raw(cls) -> "Optional[pd.DataFrame]":
        return cls._get_monthly_group(
            PPI_SERIES, PPI_CACHE_FILE, "_last_ppi_fetch"
        )

    @classmethod
    def _get_expectations(cls) -> "Optional[pd.DataFrame]":
        return cls._get_monthly_group(
            EXPECTATIONS_SERIES, EXPECTATIONS_CACHE_FILE, "_last_exp_fetch",
            max_age_days=7
        )

    @classmethod
    def _get_monthly_group(
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

    # ──────────────────────────────────────────────────────────────────────────
    # Cache helpers
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _is_cache_fresh(cls, last_date, max_age_days: int) -> bool:
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
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(cache_file)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # FRED fetch helpers
    # ──────────────────────────────────────────────────────────────────────────

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
