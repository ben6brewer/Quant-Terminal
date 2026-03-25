"""Commercial Real Estate FRED Service — CRE prices and loans."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class CreFredService(BaseFredService):
    """Fetches commercial real estate data from FRED. Quarterly, 45-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "CRE Prices": "COMREPUSQ159N",
            },
            cache_file="cre_data.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="cre", columns=["CRE Prices"]),
            ],
        ),
        FredGroup(
            series={"USREC": "USREC"},
            cache_file="cre_usrec.parquet",
            max_age_days=30,
            outputs=[FredOutput(key="usrec", columns=["USREC"])],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        cre = cls._latest_value(data, "cre", "CRE Prices")
        if cre is not None:
            result["cre_index"] = cre
        return result if result else None
