"""Energy Production FRED Service — Oil/gas extraction and stocks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class EnergyProductionFredService(BaseFredService):
    """Fetches energy production data from FRED. Monthly/weekly, 7-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Mining Production": "IPMINE",
                "WTI Crude": "DCOILWTICO",
                "USREC": "USREC",
            },
            cache_file="energy_production.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="production", columns=["Mining Production", "WTI Crude"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        extraction = cls._latest_value(data, "production", "Mining Production")
        if extraction is not None:
            result["extraction"] = extraction
        return result if result else None
