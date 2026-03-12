"""Trade FRED Service — Trade balance, exports, imports from FRED."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class TradeFredService(BaseFredService):
    """Fetches trade balance data from FRED. Monthly, 45-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Trade Balance": "BOPGSTB",
                "Exports": "BOPTEXP",
                "Imports": "BOPTIMP",
                "USREC": "USREC",
            },
            cache_file="trade_monthly.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="trade", columns=["Trade Balance", "Exports", "Imports"], unit_scale=1 / 1000),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

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
