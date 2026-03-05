"""Housing FRED Service — Housing starts, building permits from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

# ─── Series definitions ───────────────────────────────────────────────────────

HOUSING_SERIES: Dict[str, str] = {
    "Total Starts": "HOUST",
    "Single-Family": "HOUST1F",
    "5+ Units": "HOUST5F",
    "Total Permits": "PERMIT",
    "SF Permits": "PERMIT1",
    "USREC": "USREC",
}

# Cache paths
_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_HOUSING_CACHE = _CACHE_DIR / "housing_monthly.parquet"


class HousingFredService(BaseFredService):
    """
    Fetches housing starts and building permits data from FRED.

    Single monthly cache group — cache freshness: 7 days.
    """

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_housing_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        """
        Fetch all housing data, using cache when current.

        Returns dict with keys:
          "starts"  — Monthly DataFrame with Total Starts, Single-Family, 5+ Units (thousands)
          "permits" — Monthly DataFrame with Total Permits, SF Permits (thousands)
          "usrec"   — DataFrame with USREC (0/1)
        Returns None if API key missing or all fetches fail.
        """
        import pandas as pd

        raw = cls._get_group(
            HOUSING_SERIES, _HOUSING_CACHE, "_last_housing_fetch", max_age_days=7
        )

        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        starts_cols = [c for c in ["Total Starts", "Single-Family", "5+ Units"]
                       if c in raw.columns]
        if starts_cols:
            result["starts"] = raw[starts_cols].dropna(how="all")

        permits_cols = [c for c in ["Total Permits", "SF Permits"]
                        if c in raw.columns]
        if permits_cols:
            permits_df = raw[permits_cols].dropna(how="all").copy()
            if "Total Permits" in permits_df.columns and "SF Permits" in permits_df.columns:
                permits_df["Multi-Family Permits"] = permits_df["Total Permits"] - permits_df["SF Permits"]
            result["permits"] = permits_df

        if "USREC" in raw.columns:
            result["usrec"] = raw[["USREC"]].dropna(how="all")

        if not result:
            return None

        cls._data = result
        return result

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        """
        Extract latest readings for toolbar display.

        Returns dict with: total_starts, sf_starts, permits
        """
        if not data:
            return None

        result = {}

        starts_df = data.get("starts")
        if starts_df is not None:
            if "Total Starts" in starts_df.columns:
                s = starts_df["Total Starts"].dropna()
                if not s.empty:
                    result["total_starts"] = round(float(s.iloc[-1]))
            if "Single-Family" in starts_df.columns:
                s = starts_df["Single-Family"].dropna()
                if not s.empty:
                    result["sf_starts"] = round(float(s.iloc[-1]))

        permits_df = data.get("permits")
        if permits_df is not None and "Total Permits" in permits_df.columns:
            s = permits_df["Total Permits"].dropna()
            if not s.empty:
                result["total_permits"] = round(float(s.iloc[-1]))

        return result if result else None
