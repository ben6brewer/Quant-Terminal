"""Productivity FRED Service — Productivity & labor cost data from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

PROD_SERIES: Dict[str, str] = {
    "Productivity": "OPHNFB",
    "Unit Labor Costs": "ULCNFB",
    "Real Compensation": "COMPRNFB",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_PROD_CACHE = _CACHE_DIR / "productivity_quarterly.parquet"


class ProductivityFredService(BaseFredService):
    """Fetches productivity data from FRED. Quarterly, 45-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_prod_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            PROD_SERIES, _PROD_CACHE, "_last_prod_fetch", max_age_days=45
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        prod_cols = [c for c in ["Productivity", "Unit Labor Costs", "Real Compensation"]
                     if c in raw.columns]
        if prod_cols:
            result["productivity"] = raw[prod_cols].dropna(how="all")

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
        prod_df = data.get("productivity")
        if prod_df is not None:
            for col, key in [("Productivity", "productivity"),
                             ("Unit Labor Costs", "ulc")]:
                if col in prod_df.columns:
                    s = prod_df[col].dropna()
                    if len(s) >= 5:
                        yoy = s.pct_change(periods=4) * 100
                        yoy = yoy.dropna()
                        if not yoy.empty:
                            result[key] = float(yoy.iloc[-1])
        return result if result else None
