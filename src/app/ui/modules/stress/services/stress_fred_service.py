"""Stress FRED Service — Financial stress indices from FRED."""

from __future__ import annotations

from typing import Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput


class StressFredService(BaseFredService):
    """Fetches financial stress index data from FRED. Weekly, 7-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "STLFSI": "STLFSI4",
                "KCFSI": "KCFSI",
                "USREC": "USREC",
            },
            cache_file="financial_stress_weekly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="stress", columns=["STLFSI", "KCFSI"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        for col, key in [("STLFSI", "stlfsi"), ("KCFSI", "kcfsi")]:
            val = cls._latest_value(data, "stress", col)
            if val is not None:
                result[key] = val
        return result or None
