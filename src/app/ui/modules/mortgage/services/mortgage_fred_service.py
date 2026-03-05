"""Mortgage FRED Service — Mortgage rates from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

MORTGAGE_SERIES: Dict[str, str] = {
    "30Y Fixed": "MORTGAGE30US",
    "15Y Fixed": "MORTGAGE15US",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_MORTGAGE_CACHE = _CACHE_DIR / "mortgage_weekly.parquet"


class MortgageFredService(BaseFredService):
    """Fetches mortgage rate data from FRED. Weekly, 7-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_mortgage_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            MORTGAGE_SERIES, _MORTGAGE_CACHE, "_last_mortgage_fetch", max_age_days=7
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        rate_cols = [c for c in ["30Y Fixed", "15Y Fixed"] if c in raw.columns]
        if rate_cols:
            result["rates"] = raw[rate_cols].dropna(how="all")

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
        rates_df = data.get("rates")
        if rates_df is not None:
            for col, key in [("30Y Fixed", "rate_30y"), ("15Y Fixed", "rate_15y")]:
                if col in rates_df.columns:
                    s = rates_df[col].dropna()
                    if not s.empty:
                        result[key] = float(s.iloc[-1])
        return result if result else None
