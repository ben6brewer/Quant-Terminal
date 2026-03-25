"""Home Market FRED Service — Home prices and sales data from FRED."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class HomeMarketFredService(BaseFredService):
    """Fetches home price and sales data from FRED."""

    GROUPS = [
        FredGroup(
            series={
                "Case-Shiller National": "CSUSHPINSA",
                "Case-Shiller 20-City": "SPCS20RSA",
                "Median Sale Price": "MSPUS",
                "Average Sale Price": "ASPUS",
                "USREC": "USREC",
            },
            cache_file="home_prices_monthly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="prices", columns=["Case-Shiller National", "Case-Shiller 20-City"]),
                FredOutput(key="sale_prices", columns=["Median Sale Price", "Average Sale Price"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
        FredGroup(
            series={
                "Existing Home Sales": "EXHOSLUSM495S",
                "New Home Sales": "HSN1F",
                "New Supply Months": "MNMFS",
                "Existing Supply Months": "MSACSR",
                "Homeownership Rate": "RHORUSQ156N",
            },
            cache_file="home_sales_monthly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="sales_existing", columns=["Existing Home Sales"]),
                FredOutput(key="sales_new", columns=["New Home Sales"]),
                FredOutput(key="supply", columns=["New Supply Months", "Existing Supply Months"]),
                FredOutput(key="homeownership", columns=["Homeownership Rate"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        national = cls._latest_value(data, "prices", "Case-Shiller National")
        if national is not None:
            result["national"] = national
        city = cls._latest_value(data, "prices", "Case-Shiller 20-City")
        if city is not None:
            result["city"] = city
        median = cls._latest_value(data, "sale_prices", "Median Sale Price", 0)
        if median is not None:
            result["median"] = median
        avg = cls._latest_value(data, "sale_prices", "Average Sale Price", 0)
        if avg is not None:
            result["avg"] = avg
        existing = cls._latest_value(data, "sales_existing", "Existing Home Sales", 0)
        if existing is not None:
            result["existing"] = existing
        new = cls._latest_value(data, "sales_new", "New Home Sales", 0)
        if new is not None:
            result["new"] = new
        supply = cls._latest_value(data, "supply", "Existing Supply Months")
        if supply is not None:
            result["supply"] = supply
        new_supply = cls._latest_value(data, "supply", "New Supply Months")
        if new_supply is not None:
            result["new_supply"] = new_supply
        return result if result else None
