"""Mortgage FRED Service — Mortgage rates from FRED."""

from __future__ import annotations

from typing import Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput


class MortgageFredService(BaseFredService):
    """Fetches mortgage rate data from FRED. Weekly, 7-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "30Y Fixed": "MORTGAGE30US",
                "15Y Fixed": "MORTGAGE15US",
                "USREC": "USREC",
            },
            cache_file="mortgage_weekly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="rates", columns=["30Y Fixed", "15Y Fixed"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        for col, key in [("30Y Fixed", "rate_30y"), ("15Y Fixed", "rate_15y")]:
            val = cls._latest_value(data, "rates", col)
            if val is not None:
                result[key] = val
        return result or None
