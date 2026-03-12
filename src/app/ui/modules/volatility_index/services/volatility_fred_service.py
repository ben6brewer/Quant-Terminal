"""Volatility FRED Service — VIX and related volatility indices from FRED + MOVE from Yahoo."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)

VOL_SERIES: Dict[str, str] = {
    "VIX": "VIXCLS",
    "3M Vol": "VXVCLS",
    "Oil Vol": "OVXCLS",
    "NASDAQ Vol": "VXNCLS",
    "Russell Vol": "RVXCLS",
    "DJIA Vol": "VXDCLS",
    "EM Vol": "VXEEMCLS",
    "USREC": "USREC",
}

_VOL_COLS = ["VIX", "3M Vol", "Oil Vol", "NASDAQ Vol", "Russell Vol", "DJIA Vol", "EM Vol", "MOVE"]

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_VOL_CACHE = _CACHE_DIR / "volatility_daily.parquet"


class VolatilityFredService(BaseFredService):
    """Fetches volatility index data from FRED + MOVE from Yahoo. Daily, 3-day cache."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_vol_fetch: Optional[float] = None

    @classmethod
    def _fetch_move(cls) -> "Optional[pd.Series]":
        """Fetch MOVE index from Yahoo Finance. Returns None on failure."""
        try:
            from app.services.yahoo_finance_service import YahooFinanceService

            df = YahooFinanceService.fetch_full_history("^MOVE")
            if df is not None and not df.empty and "Close" in df.columns:
                s = df["Close"].dropna()
                s.name = "MOVE"
                return s
        except Exception:
            log.warning("Failed to fetch MOVE index from Yahoo", exc_info=True)
        return None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            VOL_SERIES, _VOL_CACHE, "_last_vol_fetch", max_age_days=3
        )
        if raw is None or raw.empty:
            return None

        # Fetch MOVE from Yahoo and merge with FRED data
        move = cls._fetch_move()
        if move is not None:
            raw = pd.concat([raw, move.to_frame()], axis=1)

        result: Dict[str, pd.DataFrame] = {}

        vol_cols = [c for c in _VOL_COLS if c in raw.columns]
        if vol_cols:
            result["volatility"] = raw[vol_cols].dropna(how="all")

        if "USREC" in raw.columns:
            result["usrec"] = raw[["USREC"]].dropna(how="all")

        if not result:
            return None

        cls._data = result
        return result

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}
        vol_df = data.get("volatility")
        if vol_df is not None:
            for col, key in [("VIX", "vix"), ("MOVE", "move")]:
                if col in vol_df.columns:
                    s = vol_df[col].dropna()
                    if not s.empty:
                        result[key] = float(s.iloc[-1])
        return result if result else None
