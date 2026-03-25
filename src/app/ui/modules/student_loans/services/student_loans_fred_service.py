"""Student Loans FRED Service — Total and federal student loan balances."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class StudentLoansFredService(BaseFredService):
    """Fetches student loan data from FRED. Quarterly, 45-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Total Student Loans": "SLOAS",
                "Federal Student Loans": "FGCCSAQ027S",
            },
            cache_file="student_loans_data.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="loans", columns=["Total Student Loans", "Federal Student Loans"], unit_scale=1 / 1000),
            ],
        ),
        FredGroup(
            series={"USREC": "USREC"},
            cache_file="student_loans_usrec.parquet",
            max_age_days=30,
            outputs=[FredOutput(key="usrec", columns=["USREC"])],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        total = cls._latest_value(data, "loans", "Total Student Loans")
        if total is not None:
            result["total"] = total
        federal = cls._latest_value(data, "loans", "Federal Student Loans")
        if federal is not None:
            result["federal"] = federal
        return result if result else None
