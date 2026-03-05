"""Financial Conditions FRED Service — NFCI and corporate spreads from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

FINCOND_SERIES: Dict[str, str] = {
    "NFCI": "NFCI",
    "Adjusted NFCI": "ANFCI",
    "Credit Sub": "NFCICREDIT",
    "Leverage Sub": "NFCILEVERAGE",
    "NonFin Leverage Sub": "NFCINONFINLEVERAGE",
    "Baa-10Y Spread": "BAA10Y",
    "Aaa-10Y Spread": "AAA10Y",
    "HY OAS": "BAMLH0A0HYM2",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_FINCOND_CACHE = _CACHE_DIR / "financial_conditions_weekly.parquet"


class FinancialConditionsFredService(BaseFredService):
    """Fetches financial conditions and corporate spread data from FRED."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_fincond_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            FINCOND_SERIES, _FINCOND_CACHE, "_last_fincond_fetch", max_age_days=7
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        nfci_cols = [c for c in ["NFCI", "Adjusted NFCI", "Credit Sub",
                                  "Leverage Sub", "NonFin Leverage Sub"]
                     if c in raw.columns]
        if nfci_cols:
            result["nfci"] = raw[nfci_cols].dropna(how="all")

        spread_cols = [c for c in ["Baa-10Y Spread", "Aaa-10Y Spread", "HY OAS"]
                       if c in raw.columns]
        if spread_cols:
            result["spreads"] = raw[spread_cols].dropna(how="all")

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

        nfci_df = data.get("nfci")
        if nfci_df is not None and "NFCI" in nfci_df.columns:
            s = nfci_df["NFCI"].dropna()
            if len(s) >= 2:
                result["nfci"] = float(s.iloc[-1])
                result["nfci_prev"] = float(s.iloc[-2])

        spreads_df = data.get("spreads")
        if spreads_df is not None:
            if "Baa-10Y Spread" in spreads_df.columns:
                s = spreads_df["Baa-10Y Spread"].dropna()
                if not s.empty:
                    result["baa_spread"] = float(s.iloc[-1])
            if "HY OAS" in spreads_df.columns:
                s = spreads_df["HY OAS"].dropna()
                if not s.empty:
                    result["hy_oas"] = float(s.iloc[-1])

        return result if result else None
