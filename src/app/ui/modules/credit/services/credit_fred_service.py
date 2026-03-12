"""Credit FRED Service — Delinquency rates and consumer credit from FRED."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class CreditFredService(BaseFredService):
    """Fetches credit/delinquency data from FRED."""

    GROUPS = [
        FredGroup(
            series={
                "Credit Card Delinquency": "DRCCLACBS",
                "All Loans Delinquency": "DRALACBS",
                "Consumer Loans Delinquency": "DRCLACBS",
                "USREC": "USREC",
            },
            cache_file="credit_quarterly.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(
                    key="delinquency",
                    columns=["Credit Card Delinquency", "All Loans Delinquency", "Consumer Loans Delinquency"],
                ),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
        FredGroup(
            series={
                "Total Consumer Credit": "TOTALSL",
                "Revolving Credit": "REVOLSL",
                "Nonrevolving Credit": "NONREVSL",
            },
            cache_file="consumer_credit_monthly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(
                    key="credit",
                    columns=["Total Consumer Credit", "Revolving Credit", "Nonrevolving Credit"],
                    unit_scale=1 / 1000,
                ),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}

        cc = cls._latest_value(data, "delinquency", "Credit Card Delinquency")
        if cc is not None:
            result["cc_delinquency"] = cc

        tc = cls._latest_value(data, "credit", "Total Consumer Credit")
        if tc is not None:
            result["total_credit"] = tc

        return result if result else None
