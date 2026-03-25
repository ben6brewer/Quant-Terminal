"""Loan Survey (SLOOS) FRED Service — Senior Loan Officer Opinion Survey."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class LoanSurveyFredService(BaseFredService):
    """Fetches SLOOS lending standards data from FRED. Quarterly, 45-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "C&I Large Firms": "DRTSCILM",
                "C&I Small Firms": "DRTSCIS",
                "Credit Cards": "DRTSCLCC",
                "Mortgages": "SUBLPDHMSENQ",
                "Auto Loans": "STDSAUTO",
            },
            cache_file="sloos_standards.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="standards", columns=["C&I Large Firms", "C&I Small Firms", "Credit Cards", "Mortgages", "Auto Loans"]),
            ],
        ),
        FredGroup(
            series={"USREC": "USREC"},
            cache_file="sloos_usrec.parquet",
            max_age_days=30,
            outputs=[FredOutput(key="usrec", columns=["USREC"])],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        ci = cls._latest_value(data, "standards", "C&I Large Firms")
        if ci is not None:
            result["ci_large"] = ci
        cc = cls._latest_value(data, "standards", "Credit Cards")
        if cc is not None:
            result["credit_card"] = cc
        return result if result else None
