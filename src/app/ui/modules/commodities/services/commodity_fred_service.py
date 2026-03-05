"""Commodity FRED Service — Energy prices from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

ENERGY_SERIES: Dict[str, str] = {
    "WTI Crude": "DCOILWTICO",
    "Brent Crude": "DCOILBRENTEU",
    "Natural Gas": "DHHNGSP",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_ENERGY_CACHE = _CACHE_DIR / "energy_daily.parquet"


class CommodityFredService(BaseFredService):
    """Fetches energy price data from FRED. Daily, 3-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_energy_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            ENERGY_SERIES, _ENERGY_CACHE, "_last_energy_fetch", max_age_days=3
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        energy_cols = [c for c in ["WTI Crude", "Brent Crude", "Natural Gas"]
                       if c in raw.columns]
        if energy_cols:
            result["energy"] = raw[energy_cols].dropna(how="all")

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
        energy_df = data.get("energy")
        if energy_df is not None:
            for col, key in [("WTI Crude", "wti"), ("Brent Crude", "brent"),
                             ("Natural Gas", "natgas")]:
                if col in energy_df.columns:
                    s = energy_df[col].dropna()
                    if not s.empty:
                        result[key] = float(s.iloc[-1])
        return result if result else None
