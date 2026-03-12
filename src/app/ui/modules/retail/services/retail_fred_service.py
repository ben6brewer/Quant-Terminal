"""Retail FRED Service — Retail sales and vehicle sales from FRED."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class RetailFredService(BaseFredService):
    """Fetches retail sales and vehicle sales data from FRED."""

    GROUPS = [
        FredGroup(
            series={
                "Retail Sales": "RSAFS",
                "Real Retail Sales": "RRSFS",
                "Total Vehicle Sales": "TOTALSA",
                "Light Autos": "LAUTOSA",
                "Heavy Trucks": "HTRUCKSSA",
                "USREC": "USREC",
            },
            cache_file="retail_monthly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="retail", columns=["Retail Sales", "Real Retail Sales"]),
                FredOutput(key="vehicles", columns=["Total Vehicle Sales", "Light Autos", "Heavy Trucks"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None

        result = {}

        retail_df = data.get("retail")
        if retail_df is not None:
            if "Retail Sales" in retail_df.columns:
                s = retail_df["Retail Sales"].dropna()
                if len(s) >= 2:
                    latest = float(s.iloc[-1])
                    prev = float(s.iloc[-2])
                    mom = ((latest - prev) / prev) * 100 if prev != 0 else 0
                    result["retail_total"] = latest
                    result["retail_mom"] = mom

        vehicles_df = data.get("vehicles")
        if vehicles_df is not None and "Total Vehicle Sales" in vehicles_df.columns:
            s = vehicles_df["Total Vehicle Sales"].dropna()
            if not s.empty:
                result["vehicle_total"] = float(s.iloc[-1])

        return result if result else None
