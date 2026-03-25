"""Population FRED Service — US population and demographics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class PopulationFredService(BaseFredService):
    """Fetches population data from FRED. Monthly, 45-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Total Population": "POPTHM",
                "Working Age (15-64)": "LFWA64TTUSM647S",
                "Civilian Population": "CNP16OV",
                "USREC": "USREC",
            },
            cache_file="population_monthly.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="pop_thousands", columns=["Total Population", "Civilian Population"], unit_scale=1 / 1000),
                FredOutput(key="pop_persons", columns=["Working Age (15-64)"], unit_scale=1 / 1_000_000),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        pop = cls._latest_value(data, "pop_thousands", "Total Population")
        if pop is not None:
            result["population"] = pop
        working = cls._latest_value(data, "pop_persons", "Working Age (15-64)")
        if working is not None:
            result["working_age"] = working
        return result if result else None
