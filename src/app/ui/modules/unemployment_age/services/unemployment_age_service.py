"""Unemployment by Age Group FRED Service — NSA monthly rates from BLS/FRED."""

from __future__ import annotations

from typing import Dict

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

AGE_SERIES: Dict[str, str] = {
    "16+":   "UNRATENSA",
    "16-19": "LNU04000012",
    "16-17": "LNU04000086",
    "18-19": "LNU04000088",
    "20-24": "LNU04000036",
    "25+":   "LNU04000048",
    "25-34": "LNU04000089",
    "35-44": "LNU04000091",
    "45-54": "LNU04000093",
    "55-64": "LNU04000095",
    "65+":   "LNU04000097",
}

AGE_LABELS = list(AGE_SERIES.keys())


class UnemploymentAgeService(BaseFredService):
    """Fetches US unemployment rates by age group from FRED. Monthly NSA, 45-day cache."""

    GROUPS = [
        FredGroup(
            series={
                **AGE_SERIES,
                "USREC": "USREC",
            },
            cache_file="unemployment_age_monthly.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="rates", columns=AGE_LABELS),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]
