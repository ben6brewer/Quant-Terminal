"""Recession FRED Service — Recession indicators and leading indices from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

MONTHLY_SERIES: Dict[str, str] = {
    "Recession Prob": "RECPROUSM156N",
    "Sahm Rule": "SAHMCURRENT",
    "USREC": "USREC",
    "CFNAI": "CFNAI",
    "CFNAI-MA3": "CFNAIMA3",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_MONTHLY_CACHE = _CACHE_DIR / "recession_monthly.parquet"


class RecessionFredService(BaseFredService):
    """Fetches recession indicator and leading index data from FRED. Monthly, 7-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_monthly_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            MONTHLY_SERIES, _MONTHLY_CACHE, "_last_monthly_fetch", max_age_days=7
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        recession_cols = [c for c in ["Recession Prob", "Sahm Rule"]
                          if c in raw.columns]
        if recession_cols:
            result["recession"] = raw[recession_cols].dropna(how="all")

        leading_cols = [c for c in ["CFNAI", "CFNAI-MA3"]
                        if c in raw.columns]
        if leading_cols:
            result["leading"] = raw[leading_cols].dropna(how="all")

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
        recession_df = data.get("recession")
        if recession_df is not None:
            for col, key in [("Recession Prob", "recession_prob"),
                             ("Sahm Rule", "sahm")]:
                if col in recession_df.columns:
                    s = recession_df[col].dropna()
                    if not s.empty:
                        result[key] = float(s.iloc[-1])
        return result if result else None
