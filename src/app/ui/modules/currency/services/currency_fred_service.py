"""Currency FRED Service — Dollar index and major FX pairs from FRED."""

from __future__ import annotations

from typing import Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput


class CurrencyFredService(BaseFredService):
    """Fetches currency / dollar index data from FRED. Daily, 3-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Dollar Index": "DTWEXBGS",
                "Adv. Economies": "DTWEXAFEGS",
                "EUR/USD": "DEXUSEU",
                "USD/JPY": "DEXJPUS",
                "USD/CNY": "DEXCHUS",
                "GBP/USD": "DEXUSUK",
                "USREC": "USREC",
            },
            cache_file="currency_daily.parquet",
            max_age_days=3,
            outputs=[
                FredOutput(key="dollar_index", columns=["Dollar Index", "Adv. Economies"]),
                FredOutput(key="fx_pairs", columns=["EUR/USD", "USD/JPY", "USD/CNY", "GBP/USD"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        val = cls._latest_value(data, "dollar_index", "Dollar Index")
        if val is not None:
            result["dollar_index"] = val
        val = cls._latest_value(data, "fx_pairs", "EUR/USD")
        if val is not None:
            result["eur"] = val
        return result if result else None
