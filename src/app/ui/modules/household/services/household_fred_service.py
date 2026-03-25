"""Household FRED Service — Household balance sheet data from FRED."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class HouseholdFredService(BaseFredService):
    """Fetches household balance sheet data from FRED. Quarterly, 45-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Net Worth": "BOGZ1FL192090005Q",
                "Household Debt": "CMDEBT",
                "Debt-to-GDP": "HDTGPDUSQ163N",
                "Debt Service": "TDSP",
            },
            cache_file="household_data.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="wealth", columns=["Net Worth"], unit_scale=1 / 1_000_000),
                FredOutput(key="household_debt", columns=["Household Debt"], unit_scale=1 / 1_000_000),
                FredOutput(key="debt", columns=["Debt-to-GDP", "Debt Service"]),
            ],
        ),
        FredGroup(
            series={"USREC": "USREC"},
            cache_file="household_usrec.parquet",
            max_age_days=30,
            outputs=[FredOutput(key="usrec", columns=["USREC"])],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}

        nw = cls._latest_value(data, "wealth", "Net Worth")
        if nw is not None:
            result["net_worth"] = nw

        hd = cls._latest_value(data, "household_debt", "Household Debt")
        if hd is not None:
            result["household_debt"] = hd

        dtg = cls._latest_value(data, "debt", "Debt-to-GDP")
        if dtg is not None:
            result["debt_to_gdp"] = dtg

        return result if result else None
