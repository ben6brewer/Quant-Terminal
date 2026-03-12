"""Stress FRED Service — Financial stress indices from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

STRESS_SERIES: Dict[str, str] = {
    "STLFSI": "STLFSI4",
    "KCFSI": "KCFSI",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_STRESS_CACHE = _CACHE_DIR / "financial_stress_weekly.parquet"


class StressFredService(BaseFredService):
    """Fetches financial stress index data from FRED. Weekly, 7-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_stress_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            STRESS_SERIES, _STRESS_CACHE, "_last_stress_fetch", max_age_days=7
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        stress_cols = [c for c in ["STLFSI", "KCFSI"] if c in raw.columns]
        if stress_cols:
            result["stress"] = raw[stress_cols].dropna(how="all")

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
        stress_df = data.get("stress")
        if stress_df is not None:
            for col, key in [("STLFSI", "stlfsi"), ("KCFSI", "kcfsi")]:
                if col in stress_df.columns:
                    s = stress_df[col].dropna()
                    if not s.empty:
                        result[key] = float(s.iloc[-1])
        return result if result else None
