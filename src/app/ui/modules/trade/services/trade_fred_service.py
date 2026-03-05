"""Trade FRED Service — Trade balance, exports, imports from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

TRADE_SERIES: Dict[str, str] = {
    "Trade Balance": "BOPGSTB",
    "Exports": "BOPTEXP",
    "Imports": "BOPTIMP",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_TRADE_CACHE = _CACHE_DIR / "trade_monthly.parquet"


class TradeFredService(BaseFredService):
    """Fetches trade balance data from FRED. Monthly, 45-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_trade_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            TRADE_SERIES, _TRADE_CACHE, "_last_trade_fetch", max_age_days=45
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        trade_cols = [c for c in ["Trade Balance", "Exports", "Imports"] if c in raw.columns]
        if trade_cols:
            df = raw[trade_cols].dropna(how="all").copy()
            # Convert millions to billions
            for col in df.columns:
                df[col] = df[col] / 1000.0
            result["trade"] = df

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
        trade_df = data.get("trade")
        if trade_df is not None and "Trade Balance" in trade_df.columns:
            s = trade_df["Trade Balance"].dropna()
            if len(s) >= 2:
                result["balance"] = float(s.iloc[-1])
                prev = float(s.iloc[-2])
                if prev != 0:
                    result["balance_chg"] = ((float(s.iloc[-1]) - prev) / abs(prev)) * 100
        return result if result else None
