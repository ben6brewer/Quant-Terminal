"""Regional PMI FRED Service — Regional Fed manufacturing indices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class RegionalPmiFredService(BaseFredService):
    """Fetches regional PMI data from FRED. Monthly, 7-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Empire State": "GAFDISA066MSFRBNY",
                "Philly Fed": "GACDFSA066MSFRBPHI",
                "Dallas Fed": "BACTSAMFRBDAL",
                "USREC": "USREC",
            },
            cache_file="regional_pmi_monthly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="regional", columns=["Empire State", "Philly Fed", "Dallas Fed"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        empire = cls._latest_value(data, "regional", "Empire State")
        if empire is not None:
            result["empire"] = empire
        philly = cls._latest_value(data, "regional", "Philly Fed")
        if philly is not None:
            result["philly"] = philly
        return result if result else None
