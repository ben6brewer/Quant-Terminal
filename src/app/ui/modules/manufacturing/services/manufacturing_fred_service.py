"""Manufacturing FRED Service — Durable goods orders from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

MANUFACTURING_SERIES: Dict[str, str] = {
    "Durable Goods": "DGORDER",
    "Core Capital Goods": "NEWORDER",
    "Unfilled Orders": "AMDMUO",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_MANUFACTURING_CACHE = _CACHE_DIR / "manufacturing_monthly.parquet"


class ManufacturingFredService(BaseFredService):
    """Fetches durable goods order data from FRED. Monthly, 7-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_manufacturing_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            MANUFACTURING_SERIES, _MANUFACTURING_CACHE,
            "_last_manufacturing_fetch", max_age_days=7
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        order_cols = [c for c in ["Durable Goods", "Core Capital Goods", "Unfilled Orders"]
                      if c in raw.columns]
        if order_cols:
            df = raw[order_cols].dropna(how="all").copy()
            # Convert millions to billions
            for col in df.columns:
                df[col] = df[col] / 1000.0
            result["orders"] = df

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
        orders_df = data.get("orders")
        if orders_df is not None and "Durable Goods" in orders_df.columns:
            s = orders_df["Durable Goods"].dropna()
            if len(s) >= 2:
                latest = float(s.iloc[-1])
                prev = float(s.iloc[-2])
                mom = ((latest - prev) / prev) * 100 if prev != 0 else 0
                result["dg_mom"] = mom
        return result if result else None
