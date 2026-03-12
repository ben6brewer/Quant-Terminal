"""Consumer FRED Service — University of Michigan Consumer Sentiment from FRED."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

if TYPE_CHECKING:
    import pandas as pd


class ConsumerFredService(BaseFredService):
    """
    Fetches consumer sentiment data from FRED.

    Single monthly cache group — cache freshness: 7 days.
    """

    GROUPS = [
        FredGroup(
            series={
                "Sentiment": "UMCSENT",
                "USREC": "USREC",
            },
            cache_file="consumer_monthly.parquet",
            max_age_days=7,
            outputs=[
                FredOutput(key="sentiment", columns=["Sentiment"]),
                FredOutput(key="usrec", columns=["USREC"]),
            ],
        ),
    ]

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        """
        Extract latest readings for toolbar display.

        Returns dict with: sentiment, sentiment_mom
        """
        if not data:
            return None

        result = {}

        sent_df = data.get("sentiment")
        if sent_df is not None and "Sentiment" in sent_df.columns:
            s = sent_df["Sentiment"].dropna()
            if not s.empty:
                result["sentiment"] = round(float(s.iloc[-1]), 1)
                if len(s) >= 2:
                    mom = float(s.iloc[-1]) - float(s.iloc[-2])
                    result["sentiment_mom"] = round(mom, 1)

        return result if result else None
