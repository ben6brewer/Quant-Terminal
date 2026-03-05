"""Consumer FRED Service — University of Michigan Consumer Sentiment from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

# ─── Series definitions ───────────────────────────────────────────────────────

CONSUMER_SERIES: Dict[str, str] = {
    "Sentiment": "UMCSENT",
    "USREC": "USREC",
}

# Cache paths
_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_CONSUMER_CACHE = _CACHE_DIR / "consumer_monthly.parquet"


class ConsumerFredService(BaseFredService):
    """
    Fetches consumer sentiment data from FRED.

    Single monthly cache group — cache freshness: 7 days.
    """

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_consumer_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        """
        Fetch consumer sentiment data, using cache when current.

        Returns dict with keys:
          "sentiment" — Monthly DataFrame with Sentiment (index)
          "usrec"     — DataFrame with USREC (0/1)
        Returns None if API key missing or all fetches fail.
        """
        import pandas as pd

        raw = cls._get_group(
            CONSUMER_SERIES, _CONSUMER_CACHE, "_last_consumer_fetch", max_age_days=7
        )

        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        if "Sentiment" in raw.columns:
            result["sentiment"] = raw[["Sentiment"]].dropna(how="all")

        if "USREC" in raw.columns:
            result["usrec"] = raw[["USREC"]].dropna(how="all")

        if not result:
            return None

        cls._data = result
        return result

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
