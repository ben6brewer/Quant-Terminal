"""Retail FRED Service — Retail sales and vehicle sales from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

# ─── Series definitions ───────────────────────────────────────────────────────

RETAIL_SERIES: Dict[str, str] = {
    "Retail Sales": "RSAFS",
    "Real Retail Sales": "RRSFS",
    "Total Vehicle Sales": "TOTALSA",
    "Light Autos": "LAUTOSA",
    "Heavy Trucks": "HTRUCKSSA",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_RETAIL_CACHE = _CACHE_DIR / "retail_monthly.parquet"


class RetailFredService(BaseFredService):
    """Fetches retail sales and vehicle sales data from FRED."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_retail_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            RETAIL_SERIES, _RETAIL_CACHE, "_last_retail_fetch", max_age_days=7
        )

        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        # Retail sales
        retail_cols = [c for c in ["Retail Sales", "Real Retail Sales"] if c in raw.columns]
        if retail_cols:
            result["retail"] = raw[retail_cols].dropna(how="all")

        # Vehicle sales
        vehicle_cols = [c for c in ["Total Vehicle Sales", "Light Autos", "Heavy Trucks"]
                        if c in raw.columns]
        if vehicle_cols:
            result["vehicles"] = raw[vehicle_cols].dropna(how="all")

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

        retail_df = data.get("retail")
        if retail_df is not None:
            if "Retail Sales" in retail_df.columns:
                s = retail_df["Retail Sales"].dropna()
                if len(s) >= 2:
                    latest = float(s.iloc[-1])
                    prev = float(s.iloc[-2])
                    mom = ((latest - prev) / prev) * 100 if prev != 0 else 0
                    result["retail_total"] = latest
                    result["retail_mom"] = mom

        vehicles_df = data.get("vehicles")
        if vehicles_df is not None and "Total Vehicle Sales" in vehicles_df.columns:
            s = vehicles_df["Total Vehicle Sales"].dropna()
            if not s.empty:
                result["vehicle_total"] = float(s.iloc[-1])

        return result if result else None
