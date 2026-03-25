"""Real Rates FRED Service — Real interest rates and TIPS yields."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class RealRatesFredService(BaseFredService):
    """Fetches real rates and TIPS data from FRED. Daily, 3-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "5Y TIPS": "DFII5",
                "10Y TIPS": "DFII10",
                "20Y TIPS": "DFII20",
                "30Y TIPS": "DFII30",
                "USREC": "USREC",
            },
            cache_file="real_rates_daily.parquet",
            max_age_days=3,
            outputs=[
                FredOutput(key="tips", columns=["5Y TIPS", "10Y TIPS", "20Y TIPS", "30Y TIPS"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        tips10 = cls._latest_value(data, "tips", "10Y TIPS")
        if tips10 is not None:
            result["tips10"] = tips10
        return result if result else None
