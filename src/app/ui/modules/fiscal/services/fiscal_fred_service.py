"""Fiscal FRED Service — Government debt data from FRED."""

from __future__ import annotations

from typing import Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput


class FiscalFredService(BaseFredService):
    """Fetches government debt data from FRED. Quarterly, 45-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Total Public Debt": "GFDEBTN",
                "Debt to GDP": "GFDEGDQ188S",
                "USREC": "USREC",
            },
            cache_file="fiscal_quarterly.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="debt", columns=["Total Public Debt"], unit_scale=1 / 1_000_000),
                FredOutput(key="debt_gdp", columns=["Debt to GDP"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        val = cls._latest_value(data, "debt", "Total Public Debt")
        if val is not None:
            result["debt_trillions"] = val
        val = cls._latest_value(data, "debt_gdp", "Debt to GDP")
        if val is not None:
            result["debt_gdp_pct"] = val
        return result or None
