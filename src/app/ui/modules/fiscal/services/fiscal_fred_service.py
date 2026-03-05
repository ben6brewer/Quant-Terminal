"""Fiscal FRED Service — Government debt data from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

FISCAL_SERIES: Dict[str, str] = {
    "Total Public Debt": "GFDEBTN",
    "Debt to GDP": "GFDEGDQ188S",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_FISCAL_CACHE = _CACHE_DIR / "fiscal_quarterly.parquet"


class FiscalFredService(BaseFredService):
    """Fetches government debt data from FRED. Quarterly, 45-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_fiscal_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            FISCAL_SERIES, _FISCAL_CACHE, "_last_fiscal_fetch", max_age_days=45
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        if "Total Public Debt" in raw.columns:
            df = raw[["Total Public Debt"]].dropna(how="all").copy()
            # Convert millions to trillions
            df["Total Public Debt"] = df["Total Public Debt"] / 1_000_000.0
            result["debt"] = df

        if "Debt to GDP" in raw.columns:
            result["debt_gdp"] = raw[["Debt to GDP"]].dropna(how="all")

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

        debt_df = data.get("debt")
        if debt_df is not None and "Total Public Debt" in debt_df.columns:
            s = debt_df["Total Public Debt"].dropna()
            if not s.empty:
                result["debt_trillions"] = float(s.iloc[-1])

        gdp_df = data.get("debt_gdp")
        if gdp_df is not None and "Debt to GDP" in gdp_df.columns:
            s = gdp_df["Debt to GDP"].dropna()
            if not s.empty:
                result["debt_gdp_pct"] = float(s.iloc[-1])

        return result if result else None
