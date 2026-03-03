"""Monetary Policy FRED Service — M1/M2, Fed Balance Sheet, EFFR, Reserves, M2 Velocity."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.fred_api_key_service import FredApiKeyService

if TYPE_CHECKING:
    import pandas as pd

# ─── Series definitions ───────────────────────────────────────────────────────

# Monthly: M1, M2, M2 Velocity, NBER recession indicator
MONTHLY_SERIES: Dict[str, str] = {
    "M1":        "M1SL",
    "M2":        "M2SL",
    "M2 Velocity": "M2V",
    "USREC":     "USREC",
}

# Weekly: Fed balance sheet components
WEEKLY_SERIES: Dict[str, str] = {
    "Total Assets":    "WALCL",
    "Treasuries":      "WSHOTSL",    # Securities held outright: U.S. Treasuries (was WORAL = repos)
    "MBS":             "WSHOMCB",
    "Agency Debt":     "WSHOFADSL",  # Federal agency debt securities (Fannie/Freddie bonds)
    "Loans":           "WLCFLL",     # All loans (discount window + credit facilities; crisis spikes)
    "Reserve Balances": "WRBWFRBL",
}

# EFFR series (daily target bounds, monthly effective rate)
EFFR_SERIES: Dict[str, str] = {
    "Fed Funds Rate": "FEDFUNDS",
    "Lower Target":   "DFEDTARL",
    "Upper Target":   "DFEDTARU",
}

# Cache paths
_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_MONTHLY_CACHE  = _CACHE_DIR / "monetary_monthly.parquet"
_WEEKLY_CACHE   = _CACHE_DIR / "monetary_weekly.parquet"
_EFFR_CACHE     = _CACHE_DIR / "monetary_effr.parquet"


class MonetaryFredService:
    """
    Fetches all monetary policy data from FRED.

    Class-level cache: once fetched, subsequent callers in the same session
    return instantly without hitting FRED again.

    Monthly group (M1, M2, M2V, USREC) — cache freshness: 45 days.
    Weekly group (balance sheet, reserves) — cache freshness: 7 days.
    EFFR group (Fed Funds + target bounds) — cache freshness: 7 days.
    """

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_monthly_fetch: Optional[float] = None
    _last_weekly_fetch: Optional[float] = None
    _last_effr_fetch: Optional[float] = None
    _FETCH_COOLDOWN = 3600  # 1-hour cooldown on failed fetches

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        """
        Fetch all monetary policy data, using cache when current.

        Returns dict with keys:
          "money_supply"  — Monthly DataFrame with M1, M2 (trillions USD)
          "velocity"      — Monthly/Quarterly DataFrame with M2 Velocity (ratio)
          "usrec"         — Monthly DataFrame with USREC (0/1)
          "balance_sheet" — Weekly DataFrame with Total Assets, Treasuries, MBS, Other (trillions)
          "reserves"      — Weekly DataFrame with Reserve Balances (trillions)
          "effr"          — Monthly+Daily DataFrame with Fed Funds Rate, Lower/Upper Target (%)
        Returns None if API key missing or all fetches fail.
        """
        import pandas as pd

        monthly_raw = cls._get_monthly_group()
        weekly_raw  = cls._get_weekly_group()
        effr_raw    = cls._get_effr_group()

        result: Dict[str, pd.DataFrame] = {}

        if monthly_raw is not None and not monthly_raw.empty:
            # Split monthly data into sub-datasets
            money_cols = [c for c in ["M1", "M2"] if c in monthly_raw.columns]
            if money_cols:
                supply_df = monthly_raw[money_cols].copy()
                # Convert billions → trillions
                supply_df = supply_df / 1000.0
                supply_df = supply_df.dropna(how="all")
                result["money_supply"] = supply_df

            if "M2 Velocity" in monthly_raw.columns:
                vel_df = monthly_raw[["M2 Velocity"]].dropna(how="all")
                result["velocity"] = vel_df

            if "USREC" in monthly_raw.columns:
                rec_df = monthly_raw[["USREC"]].dropna(how="all")
                result["usrec"] = rec_df

        if weekly_raw is not None and not weekly_raw.empty:
            # Build balance sheet: Total Assets, Treasuries, MBS, Agency Debt, Loans, Other (trillions)
            bs_known = ["Total Assets", "Treasuries", "MBS", "Agency Debt", "Loans"]
            bs_cols = [c for c in bs_known if c in weekly_raw.columns]
            if bs_cols:
                bs_df = weekly_raw[bs_cols].copy()
                # Convert millions → trillions
                bs_df = bs_df / 1_000_000.0
                if "Total Assets" in bs_df.columns:
                    residual = bs_df["Total Assets"].copy()
                    for comp in ["Treasuries", "MBS", "Agency Debt", "Loans"]:
                        if comp in bs_df.columns:
                            residual = residual - bs_df[comp].fillna(0)
                    bs_df["Other"] = residual.clip(lower=0)
                bs_df = bs_df.dropna(how="all")
                result["balance_sheet"] = bs_df

            if "Reserve Balances" in weekly_raw.columns:
                res_df = weekly_raw[["Reserve Balances"]].copy()
                # Convert millions → trillions
                res_df = res_df / 1_000_000.0
                res_df = res_df.dropna(how="all")
                result["reserves"] = res_df

        if effr_raw is not None and not effr_raw.empty:
            effr_cols = [c for c in ["Fed Funds Rate", "Lower Target", "Upper Target"]
                         if c in effr_raw.columns]
            if effr_cols:
                result["effr"] = effr_raw[effr_cols].dropna(how="all")

        if not result:
            return None

        cls._data = result
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Per-group getters (with cache logic)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _get_monthly_group(cls) -> "Optional[pd.DataFrame]":
        return cls._get_group(
            MONTHLY_SERIES, _MONTHLY_CACHE, "_last_monthly_fetch", max_age_days=45
        )

    @classmethod
    def _get_weekly_group(cls) -> "Optional[pd.DataFrame]":
        return cls._get_group(
            WEEKLY_SERIES, _WEEKLY_CACHE, "_last_weekly_fetch", max_age_days=7
        )

    @classmethod
    def _get_effr_group(cls) -> "Optional[pd.DataFrame]":
        return cls._get_group(
            EFFR_SERIES, _EFFR_CACHE, "_last_effr_fetch", max_age_days=7
        )

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
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
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
