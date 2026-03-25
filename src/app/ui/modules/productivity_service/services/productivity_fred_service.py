"""Productivity FRED Service — Productivity & labor cost data from FRED."""

from __future__ import annotations

from typing import Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput


class ProductivityFredService(BaseFredService):
    """Fetches productivity data from FRED. Quarterly, 45-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Productivity": "OPHNFB",
                "Unit Labor Costs": "ULCNFB",
                "Real Compensation": "COMPRNFB",
            },
            cache_file="productivity_data.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(
                    key="productivity",
                    columns=["Productivity", "Unit Labor Costs", "Real Compensation"],
                ),
            ],
        ),
        FredGroup(
            series={"USREC": "USREC"},
            cache_file="productivity_usrec.parquet",
            max_age_days=30,
            outputs=[FredOutput(key="usrec", columns=["USREC"])],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        prod_df = data.get("productivity")
        if prod_df is not None:
            for col, key in [("Productivity", "productivity"),
                             ("Unit Labor Costs", "ulc")]:
                if col in prod_df.columns:
                    s = prod_df[col].dropna()
                    if len(s) >= 5:
                        yoy = s.pct_change(periods=4) * 100
                        yoy = yoy.dropna()
                        if not yoy.empty:
                            result[key] = float(yoy.iloc[-1])
        return result if result else None
