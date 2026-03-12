"""Currency FRED Service — Dollar index and major FX pairs from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

CURRENCY_SERIES: Dict[str, str] = {
    "Dollar Index": "DTWEXBGS",
    "Adv. Economies": "DTWEXAFEGS",
    "EUR/USD": "DEXUSEU",
    "USD/JPY": "DEXJPUS",
    "USD/CNY": "DEXCHUS",
    "GBP/USD": "DEXUSUK",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_CURRENCY_CACHE = _CACHE_DIR / "currency_daily.parquet"


class CurrencyFredService(BaseFredService):
    """Fetches currency / dollar index data from FRED. Daily, 3-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_currency_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            CURRENCY_SERIES, _CURRENCY_CACHE, "_last_currency_fetch", max_age_days=3
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        dollar_cols = [c for c in ["Dollar Index", "Adv. Economies"]
                       if c in raw.columns]
        if dollar_cols:
            result["dollar_index"] = raw[dollar_cols].dropna(how="all")

        fx_cols = [c for c in ["EUR/USD", "USD/JPY", "USD/CNY", "GBP/USD"]
                   if c in raw.columns]
        if fx_cols:
            result["fx_pairs"] = raw[fx_cols].dropna(how="all")

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
        dollar_df = data.get("dollar_index")
        if dollar_df is not None and "Dollar Index" in dollar_df.columns:
            s = dollar_df["Dollar Index"].dropna()
            if not s.empty:
                result["dollar_index"] = float(s.iloc[-1])
        fx_df = data.get("fx_pairs")
        if fx_df is not None and "EUR/USD" in fx_df.columns:
            s = fx_df["EUR/USD"].dropna()
            if not s.empty:
                result["eur"] = float(s.iloc[-1])
        return result if result else None
