"""Banking FRED Service — Bank lending data from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

BANKING_SERIES: Dict[str, str] = {
    "Total Loans": "TOTLL",
    "C&I Loans": "BUSLOANS",
    "Real Estate": "REALLN",
    "Consumer": "CONSUMER",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_BANKING_CACHE = _CACHE_DIR / "banking_weekly.parquet"


class BankingFredService(BaseFredService):
    """Fetches bank lending data from FRED. Weekly, 7-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_banking_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            BANKING_SERIES, _BANKING_CACHE, "_last_banking_fetch", max_age_days=7
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        loan_cols = [c for c in ["Total Loans", "C&I Loans", "Real Estate", "Consumer"]
                     if c in raw.columns]
        if loan_cols:
            result["loans"] = raw[loan_cols].dropna(how="all")

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
        loans_df = data.get("loans")
        if loans_df is not None and "Total Loans" in loans_df.columns:
            s = loans_df["Total Loans"].dropna()
            if not s.empty:
                result["total_loans"] = float(s.iloc[-1])
        return result if result else None
