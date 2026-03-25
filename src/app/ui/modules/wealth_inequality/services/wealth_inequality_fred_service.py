"""Wealth Inequality FRED Service — Wealth distribution and income inequality."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class WealthInequalityFredService(BaseFredService):
    """Fetches wealth distribution and income inequality data from FRED."""

    GROUPS = [
        FredGroup(
            series={
                "Top 1%": "WFRBST01134",
                "90th-99th": "WFRBSN09161",
                "50th-90th": "WFRBSN40188",
                "Bottom 50%": "WFRBSB50215",
            },
            cache_file="wealth_shares_data.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="wealth_shares", columns=["Top 1%", "90th-99th", "50th-90th", "Bottom 50%"]),
            ],
        ),
        FredGroup(
            series={"USREC": "USREC"},
            cache_file="wealth_usrec.parquet",
            max_age_days=30,
            outputs=[FredOutput(key="usrec", columns=["USREC"])],
        ),
        FredGroup(
            series={
                "Median HH Income": "MEHOINUSA672N",
                "Median Personal Income": "MEPAINUSA672N",
            },
            cache_file="income_inequality_annual.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="incomes", columns=["Median HH Income", "Median Personal Income"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        top1 = cls._latest_value(data, "wealth_shares", "Top 1%")
        if top1 is not None:
            result["top1"] = top1
        bottom50 = cls._latest_value(data, "wealth_shares", "Bottom 50%")
        if bottom50 is not None:
            result["bottom50"] = bottom50
        hh = cls._latest_value(data, "incomes", "Median HH Income", 0)
        if hh is not None:
            result["hh_income"] = hh
        return result if result else None
