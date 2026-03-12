"""Labor Market FRED Service - Fetches US labor market data from FRED API with parquet caching."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

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

# Labor force participation rates (monthly %)
PARTICIPATION_SERIES: Dict[str, str] = {
    "LFPR": "CIVPART",
    "Prime Age LFPR": "LNS11300060",
    "Emp-Pop Ratio": "EMRATIO",
}

# All monthly series combined
ALL_MONTHLY_SERIES: Dict[str, str] = {
    **RATE_SERIES,
    **PAYROLL_SERIES,
    **JOLTS_SERIES,
    **RECESSION_SERIES,
    **PARTICIPATION_SERIES,
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
_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
MONTHLY_CACHE_FILE = _CACHE_DIR / "unemployment_monthly.parquet"
WEEKLY_CACHE_FILE = _CACHE_DIR / "unemployment_weekly.parquet"


class LaborMarketFredService(BaseFredService):
    """
    Fetches US labor market data from FRED API.

    Monthly series are cached for 45 days; weekly claims for 7 days.
    Returns a dict with separate DataFrames for each data group.
    """

    _last_monthly_fetch: Optional[float] = None
    _last_weekly_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        """
        Fetch all labor market data series, using cache when current.

        Returns dict with keys:
          "rates"          - DataFrame (monthly %, DatetimeIndex)
          "payroll_levels" - DataFrame (monthly, thousands, DatetimeIndex)
          "jolts"          - DataFrame (monthly, thousands, DatetimeIndex)
          "usrec"          - Series (monthly, 0/1, DatetimeIndex)
          "claims"         - DataFrame (weekly, DatetimeIndex)
        Returns None if API key missing or all fetches fail.
        """
        monthly_df = cls._get_group(
            ALL_MONTHLY_SERIES, MONTHLY_CACHE_FILE, "_last_monthly_fetch", max_age_days=45
        )
        claims_df = cls._get_group(
            CLAIMS_SERIES, WEEKLY_CACHE_FILE, "_last_weekly_fetch", max_age_days=7
        )

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
            participation_cols = [c for c in PARTICIPATION_SERIES if c in monthly_df.columns]
            if participation_cols:
                result["participation"] = monthly_df[participation_cols]
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

        rates = data.get("rates")
        if rates is not None and "U-3" in rates.columns:
            last = rates["U-3"].dropna()
            if not last.empty:
                result["unrate"] = round(float(last.iloc[-1]), 1)
                result["date"] = last.index[-1].strftime("%b %Y")

        payrolls = data.get("payroll_levels")
        if payrolls is not None and "Total Nonfarm" in payrolls.columns:
            total = payrolls["Total Nonfarm"].dropna()
            if len(total) >= 2:
                delta = float(total.iloc[-1]) - float(total.iloc[-2])
                result["payrolls_mom"] = round(delta)

        claims = data.get("claims")
        if claims is not None and "Initial Claims" in claims.columns:
            ic = claims["Initial Claims"].dropna()
            if not ic.empty:
                result["claims"] = round(float(ic.iloc[-1]))
        if claims is not None and "IC 4-Week MA" in claims.columns:
            ma = claims["IC 4-Week MA"].dropna()
            if not ma.empty:
                result["claims_4wma"] = round(float(ma.iloc[-1]))

        jolts = data.get("jolts")
        if jolts is not None and "Job Openings" in jolts.columns:
            openings = jolts["Job Openings"].dropna()
            if not openings.empty:
                result["openings"] = round(float(openings.iloc[-1]))

        return result if result else None
