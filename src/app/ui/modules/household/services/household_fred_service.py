"""Household FRED Service — Household balance sheet data from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

HOUSEHOLD_SERIES: Dict[str, str] = {
    "Net Worth": "BOGZ1FL192090005Q",
    "Household Debt": "CMDEBT",
    "Debt-to-GDP": "HDTGPDUSQ163N",
    "Debt Service": "TDSP",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_HOUSEHOLD_CACHE = _CACHE_DIR / "household_quarterly.parquet"


class HouseholdFredService(BaseFredService):
    """Fetches household balance sheet data from FRED. Quarterly, 45-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_household_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            HOUSEHOLD_SERIES, _HOUSEHOLD_CACHE, "_last_household_fetch", max_age_days=45
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        # Net Worth: millions -> trillions
        if "Net Worth" in raw.columns:
            nw = raw[["Net Worth"]].dropna(how="all").copy()
            nw["Net Worth"] = nw["Net Worth"] / 1_000_000
            result["wealth"] = nw

        # Household Debt: millions -> trillions
        if "Household Debt" in raw.columns:
            hd = raw[["Household Debt"]].dropna(how="all").copy()
            hd["Household Debt"] = hd["Household Debt"] / 1_000_000
            result["household_debt"] = hd

        # Debt metrics
        debt_cols = [c for c in ["Debt-to-GDP", "Debt Service"] if c in raw.columns]
        if debt_cols:
            result["debt"] = raw[debt_cols].dropna(how="all")

        if "USREC" in raw.columns:
            result["usrec"] = raw[["USREC"]].dropna(how="all")

        if not result:
            return None

        cls._data = result
        return result

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}

        wealth_df = data.get("wealth")
        if wealth_df is not None and "Net Worth" in wealth_df.columns:
            s = wealth_df["Net Worth"].dropna()
            if not s.empty:
                result["net_worth"] = float(s.iloc[-1])

        hd_df = data.get("household_debt")
        if hd_df is not None and "Household Debt" in hd_df.columns:
            s = hd_df["Household Debt"].dropna()
            if not s.empty:
                result["household_debt"] = float(s.iloc[-1])

        debt_df = data.get("debt")
        if debt_df is not None and "Debt-to-GDP" in debt_df.columns:
            s = debt_df["Debt-to-GDP"].dropna()
            if not s.empty:
                result["debt_to_gdp"] = float(s.iloc[-1])

        return result if result else None
