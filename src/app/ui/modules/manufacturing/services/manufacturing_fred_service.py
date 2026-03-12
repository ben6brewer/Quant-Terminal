"""Manufacturing FRED Service — Durable goods orders from FRED."""

from __future__ import annotations

from typing import Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput


class ManufacturingFredService(BaseFredService):
    """Fetches durable goods order data from FRED. Monthly, 7-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Durable Goods": "DGORDER",
                "Core Capital Goods": "NEWORDER",
                "Unfilled Orders": "AMDMUO",
                "USREC": "USREC",
            },
            cache_file="manufacturing_monthly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(
                    key="orders",
                    columns=["Durable Goods", "Core Capital Goods", "Unfilled Orders"],
                    unit_scale=1 / 1000.0,  # millions → billions
                ),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        orders_df = data.get("orders")
        if orders_df is not None and "Durable Goods" in orders_df.columns:
            s = orders_df["Durable Goods"].dropna()
            if len(s) >= 2:
                latest = float(s.iloc[-1])
                prev = float(s.iloc[-2])
                mom = ((latest - prev) / prev) * 100 if prev != 0 else 0
                result["dg_mom"] = mom
        return result if result else None
