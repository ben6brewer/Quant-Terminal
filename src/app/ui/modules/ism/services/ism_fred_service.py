"""ISM FRED Service — ISM Manufacturing & Services PMI data from FRED."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

ISM_SERIES: Dict[str, str] = {
    "PMI": "NAPM",
    "New Orders": "NAPMNOI",
    "Employment": "NAPMEI",
    "Services Activity": "NMFBAI",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_ISM_CACHE = _CACHE_DIR / "ism_monthly.parquet"


class IsmFredService(BaseFredService):
    """Fetches ISM Manufacturing & Services data from FRED. Monthly, 7-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_ism_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            ISM_SERIES, _ISM_CACHE,
            "_last_ism_fetch", max_age_days=7,
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        # Manufacturing: PMI, New Orders, Employment
        mfg_cols = [c for c in ["PMI", "New Orders", "Employment"] if c in raw.columns]
        if mfg_cols:
            result["manufacturing"] = raw[mfg_cols].dropna(how="all").copy()

        # Services: Services Activity
        if "Services Activity" in raw.columns:
            result["services"] = raw[["Services Activity"]].dropna(how="all").copy()

        # Recession indicator
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

        mfg_df = data.get("manufacturing")
        if mfg_df is not None and "PMI" in mfg_df.columns:
            s = mfg_df["PMI"].dropna()
            if not s.empty:
                result["pmi"] = float(s.iloc[-1])

        svc_df = data.get("services")
        if svc_df is not None and "Services Activity" in svc_df.columns:
            s = svc_df["Services Activity"].dropna()
            if not s.empty:
                result["services"] = float(s.iloc[-1])

        return result if result else None
