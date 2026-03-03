"""Labor Market FRED Service - Fetches US labor market data from FRED API with parquet caching."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.fred_api_key_service import FredApiKeyService

if TYPE_CHECKING:
    import pandas as pd

# ─── Series definitions ───────────────────────────────────────────────────────

# Unemployment rates (monthly %)
RATE_SERIES: Dict[str, str] = {
    "U-3": "UNRATE",
    "U-6": "U6RATE",
    "White": "LNS14000003",
    "Black": "LNS14000006",
    "Hispanic": "LNS14000009",
    "Men 20+": "LNS14000024",
    "Women 20+": "LNS14000025",
    "Youth (16-24)": "LNU04000012",
}

# Payroll levels in thousands (monthly)
PAYROLL_SERIES: Dict[str, str] = {
    "Total Nonfarm": "PAYEMS",
    "Construction": "USCONS",
    "Manufacturing": "MANEMP",
    "Financial Activities": "USFIRE",
    "Prof & Business Svcs": "USPBS",
    "Education & Health": "USEHS",
    "Leisure & Hospitality": "USLAH",
    "Information": "USINFO",
    "Government": "USGOVT",
}

# JOLTS series in thousands (monthly)
JOLTS_SERIES: Dict[str, str] = {
    "Job Openings": "JTSJOL",
    "Hires": "JTSHIL",
    "Quits": "JTSQUL",
    "Layoffs": "JTSLDR",
}

# NBER recession indicator (monthly, 0 or 1)
RECESSION_SERIES: Dict[str, str] = {
    "USREC": "USREC",
}

# All monthly series combined
ALL_MONTHLY_SERIES: Dict[str, str] = {
    **RATE_SERIES,
    **PAYROLL_SERIES,
    **JOLTS_SERIES,
    **RECESSION_SERIES,
}

# Weekly claims series
CLAIMS_SERIES: Dict[str, str] = {
    "Initial Claims": "ICSA",
    "Continued Claims": "CCSA",
    "IC 4-Week MA": "IC4WSA",
}

# Sector labels for stacked bar (excludes Total Nonfarm)
SECTOR_LABELS = [
    "Education & Health",
    "Leisure & Hospitality",
    "Prof & Business Svcs",
    "Government",
    "Financial Activities",
    "Construction",
    "Manufacturing",
    "Information",
]

# Cache paths (reuse existing cache files for continuity)
CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
MONTHLY_CACHE_FILE = CACHE_DIR / "unemployment_monthly.parquet"
WEEKLY_CACHE_FILE = CACHE_DIR / "unemployment_weekly.parquet"


class LaborMarketFredService:
    """
    Fetches US labor market data from FRED API.

    Monthly series are cached for 45 days; weekly claims for 7 days.
    Returns a dict with separate DataFrames for each data group.
    """

    _last_monthly_fetch: Optional[float] = None
    _last_weekly_fetch: Optional[float] = None
    _FETCH_COOLDOWN = 3600  # 1 hour cooldown on failed fetches

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        """
        Fetch all labor market data series, using cache when current.

        Returns:
            Dict with keys:
              "rates"          - DataFrame (monthly %, DatetimeIndex)
              "payroll_levels" - DataFrame (monthly, thousands, DatetimeIndex)
              "jolts"          - DataFrame (monthly, thousands, DatetimeIndex)
              "usrec"          - Series (monthly, 0/1, DatetimeIndex)
              "claims"         - DataFrame (weekly, DatetimeIndex)
            Returns None if API key missing or all fetches fail.
        """
        monthly_df = cls._get_monthly_data()
        claims_df = cls._get_claims_data()

        if monthly_df is None and claims_df is None:
            return None

        result = {}

        if monthly_df is not None:
            rate_cols = [c for c in RATE_SERIES if c in monthly_df.columns]
            payroll_cols = [c for c in PAYROLL_SERIES if c in monthly_df.columns]
            jolts_cols = [c for c in JOLTS_SERIES if c in monthly_df.columns]

            if rate_cols:
                result["rates"] = monthly_df[rate_cols]
            if payroll_cols:
                result["payroll_levels"] = monthly_df[payroll_cols]
            if jolts_cols:
                result["jolts"] = monthly_df[jolts_cols]
            if "USREC" in monthly_df.columns:
                result["usrec"] = monthly_df["USREC"]

        if claims_df is not None:
            result["claims"] = claims_df

        return result if result else None

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        """
        Extract the most recent values for toolbar/overview display.

        Returns dict with: unrate, payrolls_mom, claims, claims_4wma, openings, date
        """
        if not data:
            return None

        result = {}

        # UNRATE
        rates = data.get("rates")
        if rates is not None and "U-3" in rates.columns:
            last = rates["U-3"].dropna()
            if not last.empty:
                result["unrate"] = round(float(last.iloc[-1]), 1)
                result["date"] = last.index[-1].strftime("%b %Y")

        # Payrolls MoM (in thousands)
        payrolls = data.get("payroll_levels")
        if payrolls is not None and "Total Nonfarm" in payrolls.columns:
            total = payrolls["Total Nonfarm"].dropna()
            if len(total) >= 2:
                delta = float(total.iloc[-1]) - float(total.iloc[-2])
                result["payrolls_mom"] = round(delta)

        # Initial claims
        claims = data.get("claims")
        if claims is not None and "Initial Claims" in claims.columns:
            ic = claims["Initial Claims"].dropna()
            if not ic.empty:
                result["claims"] = round(float(ic.iloc[-1]))
        if claims is not None and "IC 4-Week MA" in claims.columns:
            ma = claims["IC 4-Week MA"].dropna()
            if not ma.empty:
                result["claims_4wma"] = round(float(ma.iloc[-1]))

        # JOLTS openings
        jolts = data.get("jolts")
        if jolts is not None and "Job Openings" in jolts.columns:
            openings = jolts["Job Openings"].dropna()
            if not openings.empty:
                result["openings"] = round(float(openings.iloc[-1]))

        return result if result else None

    # ──────────────────────────────────────────────────────────────────────────
    # Monthly data
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _get_monthly_data(cls) -> "Optional[pd.DataFrame]":
        """Get monthly series, using cache when fresh (45 days)."""
        import time

        cached = cls._load_monthly_cache()
        if cached is not None:
            last_date = cached.index.max().date()
            if cls._is_monthly_cache_fresh(last_date):
                return cached

            if cls._last_monthly_fetch is not None:
                elapsed = time.monotonic() - cls._last_monthly_fetch
                if elapsed < cls._FETCH_COOLDOWN:
                    return cached

            cls._last_monthly_fetch = time.monotonic()
            updated = cls._fetch_incremental(cached, ALL_MONTHLY_SERIES, MONTHLY_CACHE_FILE)
            if updated is not None:
                return updated

        return cls._fetch_full(ALL_MONTHLY_SERIES, MONTHLY_CACHE_FILE)

    @classmethod
    def _is_monthly_cache_fresh(cls, last_date) -> bool:
        from datetime import date, timedelta
        return last_date >= (date.today() - timedelta(days=45))

    @classmethod
    def _load_monthly_cache(cls) -> "Optional[pd.DataFrame]":
        import pandas as pd
        if not MONTHLY_CACHE_FILE.exists():
            return None
        try:
            df = pd.read_parquet(MONTHLY_CACHE_FILE)
            if df.empty:
                return None
            valid_cols = [c for c in df.columns if c in ALL_MONTHLY_SERIES]
            return df[valid_cols] if valid_cols else None
        except Exception:
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Weekly claims data
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _get_claims_data(cls) -> "Optional[pd.DataFrame]":
        """Get weekly claims series, using cache when fresh (7 days)."""
        import time

        cached = cls._load_weekly_cache()
        if cached is not None:
            last_date = cached.index.max().date()
            if cls._is_weekly_cache_fresh(last_date):
                return cached

            if cls._last_weekly_fetch is not None:
                elapsed = time.monotonic() - cls._last_weekly_fetch
                if elapsed < cls._FETCH_COOLDOWN:
                    return cached

            cls._last_weekly_fetch = time.monotonic()
            updated = cls._fetch_incremental(cached, CLAIMS_SERIES, WEEKLY_CACHE_FILE)
            if updated is not None:
                return updated

        return cls._fetch_full(CLAIMS_SERIES, WEEKLY_CACHE_FILE)

    @classmethod
    def _is_weekly_cache_fresh(cls, last_date) -> bool:
        from datetime import date, timedelta
        return last_date >= (date.today() - timedelta(days=7))

    @classmethod
    def _load_weekly_cache(cls) -> "Optional[pd.DataFrame]":
        import pandas as pd
        if not WEEKLY_CACHE_FILE.exists():
            return None
        try:
            df = pd.read_parquet(WEEKLY_CACHE_FILE)
            if df.empty:
                return None
            valid_cols = [c for c in df.columns if c in CLAIMS_SERIES]
            return df[valid_cols] if valid_cols else None
        except Exception:
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Generic fetch helpers
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _fetch_full(cls, series_map: Dict[str, str], cache_file: Path) -> "Optional[pd.DataFrame]":
        """Fetch full history for a set of series from FRED."""
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
            new_last_date = combined.index.max()
            if new_last_date > last_date:
                cls._last_monthly_fetch = None
                cls._last_weekly_fetch = None
            return combined

        except Exception:
            return cached

    @classmethod
    def _save_cache(cls, df: "pd.DataFrame", cache_file: Path) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(cache_file)
        except Exception:
            pass
