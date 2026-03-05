"""Credit FRED Service — Delinquency rates and consumer credit from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

DELINQUENCY_SERIES: Dict[str, str] = {
    "Credit Card Delinquency": "DRCCLACBS",
    "All Loans Delinquency": "DRALACBS",
    "Consumer Loans Delinquency": "DRCLACBS",
    "USREC": "USREC",
}

CONSUMER_CREDIT_SERIES: Dict[str, str] = {
    "Total Consumer Credit": "TOTALSL",
    "Revolving Credit": "REVOLSL",
    "Nonrevolving Credit": "NONREVSL",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_DELINQUENCY_CACHE = _CACHE_DIR / "credit_quarterly.parquet"
_CONSUMER_CREDIT_CACHE = _CACHE_DIR / "consumer_credit_monthly.parquet"


class CreditFredService(BaseFredService):
    """Fetches credit/delinquency data from FRED."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_delinquency_fetch: Optional[float] = None
    _last_consumer_credit_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw_delinquency = cls._get_group(
            DELINQUENCY_SERIES, _DELINQUENCY_CACHE,
            "_last_delinquency_fetch", max_age_days=45
        )
        raw_credit = cls._get_group(
            CONSUMER_CREDIT_SERIES, _CONSUMER_CREDIT_CACHE,
            "_last_consumer_credit_fetch", max_age_days=7
        )

        if raw_delinquency is None and raw_credit is None:
            return None

        result: Dict[str, pd.DataFrame] = {}

        if raw_delinquency is not None and not raw_delinquency.empty:
            delinq_cols = [c for c in ["Credit Card Delinquency", "All Loans Delinquency",
                                        "Consumer Loans Delinquency"]
                           if c in raw_delinquency.columns]
            if delinq_cols:
                result["delinquency"] = raw_delinquency[delinq_cols].dropna(how="all")

            if "USREC" in raw_delinquency.columns:
                result["usrec"] = raw_delinquency[["USREC"]].dropna(how="all")

        if raw_credit is not None and not raw_credit.empty:
            credit_cols = [c for c in ["Total Consumer Credit", "Revolving Credit",
                                        "Nonrevolving Credit"]
                           if c in raw_credit.columns]
            if credit_cols:
                df = raw_credit[credit_cols].dropna(how="all").copy()
                # Convert billions to trillions
                for col in df.columns:
                    df[col] = df[col] / 1000.0
                result["credit"] = df

        if not result:
            return None

        cls._data = result
        return result

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}

        delinq_df = data.get("delinquency")
        if delinq_df is not None and "Credit Card Delinquency" in delinq_df.columns:
            s = delinq_df["Credit Card Delinquency"].dropna()
            if not s.empty:
                result["cc_delinquency"] = float(s.iloc[-1])

        credit_df = data.get("credit")
        if credit_df is not None and "Total Consumer Credit" in credit_df.columns:
            s = credit_df["Total Consumer Credit"].dropna()
            if not s.empty:
                result["total_credit"] = float(s.iloc[-1])

        return result if result else None
