"""Commodity FRED Service — Energy prices from FRED."""

from __future__ import annotations

from typing import Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput


class CommodityFredService(BaseFredService):
    """Fetches energy price data from FRED. Daily, 3-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "WTI Crude": "DCOILWTICO",
                "Brent Crude": "DCOILBRENTEU",
                "Natural Gas": "DHHNGSP",
                "USREC": "USREC",
            },
            cache_file="energy_daily.parquet",
            max_age_days=3,
            outputs=[
                FredOutput(key="energy", columns=["WTI Crude", "Brent Crude", "Natural Gas"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        for col, key in [("WTI Crude", "wti"), ("Brent Crude", "brent"),
                         ("Natural Gas", "natgas")]:
            val = cls._latest_value(data, "energy", col)
            if val is not None:
                result[key] = val
        return result or None
