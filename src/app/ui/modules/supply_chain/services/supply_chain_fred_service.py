"""Supply Chain FRED Service — Inventory/sales ratios."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class SupplyChainFredService(BaseFredService):
    """Fetches inventory/sales ratio data from FRED. Monthly, 7-day cache."""

    GROUPS = [
        FredGroup(
            series={
                "Total I/S Ratio": "ISRATIO",
                "Retail I/S": "RETAILIRSA",
                "Manufacturing I/S": "MNFCTRIRSA",
                "Wholesale I/S": "WHLSLRIRSA",
                "USREC": "USREC",
            },
            cache_file="inventories_ratios.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="inventories", columns=["Total I/S Ratio", "Retail I/S", "Manufacturing I/S", "Wholesale I/S"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        total = cls._latest_value(data, "inventories", "Total I/S Ratio", 3)
        if total is not None:
            result["total_is"] = total
        return result if result else None
