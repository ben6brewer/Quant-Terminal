"""Banking FRED Service — Bank lending data from FRED."""

from __future__ import annotations

from typing import Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput


class BankingFredService(BaseFredService):
    """Fetches bank lending data from FRED. Weekly, 7-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Total Loans": "TOTLL",
                "C&I Loans": "BUSLOANS",
                "Real Estate": "REALLN",
                "Consumer": "CONSUMER",
                "USREC": "USREC",
            },
            cache_file="banking_weekly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="loans", columns=["Total Loans", "C&I Loans", "Real Estate", "Consumer"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        val = cls._latest_value(data, "loans", "Total Loans")
        if val is not None:
            return {"total_loans": val}
        return None
