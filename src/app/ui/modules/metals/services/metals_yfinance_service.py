"""Metals YFinance Service — Gold, Silver, Copper, Platinum, Palladium futures."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    import pandas as pd

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache"
_METALS_CACHE = _CACHE_DIR / "metals_futures.parquet"

TICKERS = {
    "GC=F": "Gold",
    "SI=F": "Silver",
    "HG=F": "Copper",
    "PL=F": "Platinum",
    "PA=F": "Palladium",
}

_MAX_AGE_SECONDS = 86400  # 1 day

logger = logging.getLogger(__name__)


class MetalsYFinanceService:
    """Fetches commodity metal futures prices via yfinance."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        now = time.time()

        # In-memory cache
        if cls._data is not None and cls._last_fetch is not None:
            if now - cls._last_fetch < _MAX_AGE_SECONDS:
                return cls._data

        # Disk cache
        metals_df = cls._load_cache(now)

        if metals_df is None:
            metals_df = cls._fetch_from_yfinance()
            if metals_df is not None and not metals_df.empty:
                cls._save_cache(metals_df)

        if metals_df is None or metals_df.empty:
            return None

        result = {"metals": metals_df}
        cls._data = result
        cls._last_fetch = now
        return result

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        metals_df = data.get("metals")
        if metals_df is None or metals_df.empty:
            return None

        result = {}
        for col in ["Gold", "Silver", "Copper", "Platinum", "Palladium"]:
            if col in metals_df.columns:
                s = metals_df[col].dropna()
                if not s.empty:
                    result[col.lower()] = float(s.iloc[-1])
        return result if result else None

    @classmethod
    def _load_cache(cls, now: float) -> "Optional[pd.DataFrame]":
        import pandas as pd

        if not _METALS_CACHE.exists():
            return None
        try:
            age = now - _METALS_CACHE.stat().st_mtime
            if age > _MAX_AGE_SECONDS:
                return None
            df = pd.read_parquet(_METALS_CACHE)
            if df.empty:
                return None
            return df
        except Exception as e:
            logger.warning("Failed to load metals cache: %s", e)
            return None

    @classmethod
    def _save_cache(cls, df: "pd.DataFrame"):
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(_METALS_CACHE)
        except Exception as e:
            logger.warning("Failed to save metals cache: %s", e)

    @classmethod
    def _fetch_from_yfinance(cls) -> "Optional[pd.DataFrame]":
        import pandas as pd

        try:
            import yfinance as yf

            tickers_list = list(TICKERS.keys())
            raw = yf.download(tickers_list, period="max", progress=False)

            if raw is None or raw.empty:
                return None

            # yf.download returns MultiIndex columns (Price, Ticker) for multiple tickers
            if isinstance(raw.columns, pd.MultiIndex):
                close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else None
                if close is None:
                    return None
                # Rename ticker symbols to friendly names
                rename_map = {t: TICKERS[t] for t in tickers_list if t in close.columns}
                close = close.rename(columns=rename_map)
            else:
                # Single ticker fallback
                close = raw[["Close"]].rename(columns={"Close": list(TICKERS.values())[0]})

            # Keep only the metals columns we expect
            expected = list(TICKERS.values())
            cols = [c for c in expected if c in close.columns]
            if not cols:
                return None

            metals_df = close[cols].copy()
            metals_df.index = pd.DatetimeIndex(metals_df.index)
            metals_df = metals_df.ffill()  # forward-fill gaps

            return metals_df

        except Exception as e:
            logger.error("Failed to fetch metals from yfinance: %s", e)
            return None
