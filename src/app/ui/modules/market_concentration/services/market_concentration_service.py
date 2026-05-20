"""Market Concentration Service — S&P 500 historical concentration metrics.

Computes two concentration metrics for the S&P 500 using current
constituents + Yahoo Finance historical prices and current shares
outstanding:
  - Top N % market cap share (for N = 1..100)
  - HHI (Herfindahl-Hirschman Index, sum(weights^2) * 10,000)

Approximations:
  1. Uses CURRENT S&P 500 membership for the entire history (~3-5%
     survivorship bias; trend is preserved).
  2. Treats shares outstanding as constant (small error from buybacks).
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "market_concentration"

_CONSTITUENTS_CACHE = _CACHE_DIR / "sp500_constituents.json"
_SHARES_CACHE = _CACHE_DIR / "shares_outstanding.json"
_PRICES_CACHE = _CACHE_DIR / "prices.parquet"
# v2 result cache: was bumped from MAX_N=100 → 1000 so v1 files are stale.
_RESULT_CACHE = _CACHE_DIR / "concentration_v2.parquet"
_HHI_CACHE = _CACHE_DIR / "hhi_v2.parquet"
# Legacy files — deleted opportunistically on save.
_LEGACY_FILES = (
    _CACHE_DIR / "top_n_returns.parquet",
    _CACHE_DIR / "concentration.parquet",
    _CACHE_DIR / "hhi.parquet",
)

_CONSTITUENTS_MAX_AGE = 7 * 86400   # 7 days
_SHARES_MAX_AGE = 7 * 86400         # 7 days
_PRICES_MAX_AGE = 86400             # 1 day
_RESULT_MAX_AGE = 86400             # 1 day

# Top-N range we precompute. Covers any N the spinbox can produce, sized to
# accommodate larger indices (Russell 1000) without re-engineering. The actual
# stored width is min(MAX_N, ticker_count).
MAX_N = 1000


class MarketConcentrationService:
    """Fetches S&P 500 history and computes concentration metrics."""

    # In-memory cache of the final result dict
    _data: Optional[Dict] = None
    _last_fetch: Optional[float] = None

    # Progress tracking — read from main thread via QTimer polling
    progress_stage: str = ""
    progress_current: int = 0
    progress_total: int = 0

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict]:
        """Top-level entry point. Returns dict with sorted_weights, hhi,
        effective_n, top_n_returns_pct, ticker_count, as_of."""
        import pandas as pd

        now = time.time()

        # In-memory cache
        if cls._data is not None and cls._last_fetch is not None:
            if now - cls._last_fetch < _RESULT_MAX_AGE:
                return cls._data

        # Try loading the precomputed result from disk
        cached = cls._load_result_cache(now)
        if cached is not None:
            cls._data = cached
            cls._last_fetch = now
            return cached

        # Otherwise, full fetch + compute
        cls.progress_stage = "Fetching S&P 500 constituent list"
        cls.progress_current = 0
        cls.progress_total = 0

        tickers = cls._fetch_constituents()
        if not tickers:
            logger.error("No S&P 500 constituents available")
            return None

        cls.progress_stage = f"Fetching shares outstanding for {len(tickers)} tickers"
        cls.progress_current = 0
        cls.progress_total = len(tickers)
        shares = cls._fetch_shares_outstanding(tickers)
        if not shares:
            logger.error("No shares outstanding data available")
            return None

        cls.progress_stage = f"Downloading price history for {len(tickers)} tickers"
        cls.progress_current = 0
        cls.progress_total = 0
        prices = cls._fetch_prices(tickers, now)
        if prices is None or prices.empty:
            logger.error("No price data available")
            return None

        cls.progress_stage = "Computing concentration metrics"
        result = cls._compute_concentration(prices, shares)
        if result is None:
            return None

        cls._save_result_cache(result)
        cls._data = result
        cls._last_fetch = now
        return result

    # ── Constituents ──────────────────────────────────────────────────────

    @classmethod
    def _fetch_constituents(cls) -> List[str]:
        """Get current S&P 500 tickers. Reuses Stock Heatmap's Wikipedia
        scraper to avoid duplicating logic."""
        # Try our own cache first
        if _CONSTITUENTS_CACHE.exists():
            try:
                age = time.time() - _CONSTITUENTS_CACHE.stat().st_mtime
                if age < _CONSTITUENTS_MAX_AGE:
                    with open(_CONSTITUENTS_CACHE, "r") as f:
                        cached = json.load(f)
                    if isinstance(cached, list) and cached:
                        return cached
            except Exception as e:
                logger.warning("Failed to load constituents cache: %s", e)

        # Reuse the Stock Heatmap Wikipedia scraper
        try:
            from app.ui.modules.stock_heatmap.services.sp500_heatmap_service import (
                SP500HeatmapService,
            )
            df = SP500HeatmapService._scrape_wikipedia(
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                "sp500",
                {"Symbol": "ticker", "Security": "name",
                 "GICS Sector": "sector", "GICS Sub-Industry": "sub_industry"},
                table_index=0,
            )
            if df is None or df.empty:
                return []
            tickers = df["ticker"].tolist()
            # Persist to our cache
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(_CONSTITUENTS_CACHE, "w") as f:
                json.dump(tickers, f)
            return tickers
        except Exception as e:
            logger.error("Failed to fetch constituents: %s", e)
            return []

    # ── Shares outstanding ────────────────────────────────────────────────

    @classmethod
    def _fetch_shares_outstanding(cls, tickers: List[str]) -> Dict[str, float]:
        """Fetch sharesOutstanding from yfinance .info for each ticker.
        Cached to its own JSON to avoid touching TickerMetadataService."""
        # Try cache first
        cached: Dict[str, float] = {}
        if _SHARES_CACHE.exists():
            try:
                age = time.time() - _SHARES_CACHE.stat().st_mtime
                if age < _SHARES_MAX_AGE:
                    with open(_SHARES_CACHE, "r") as f:
                        cached = json.load(f)
                    if cached:
                        # Ensure we have shares for the current ticker set
                        missing = [t for t in tickers if t not in cached]
                        if not missing:
                            cls.progress_current = len(tickers)
                            return {t: float(cached[t]) for t in tickers if cached.get(t)}
            except Exception as e:
                logger.warning("Failed to load shares cache: %s", e)
                cached = {}

        # Fetch in parallel via yfinance .info
        from app.services.yahoo_finance_service import YahooFinanceService

        result: Dict[str, float] = dict(cached) if cached else {}
        to_fetch = [t for t in tickers if t not in result]

        if not to_fetch:
            cls.progress_current = len(tickers)
            return result

        cls.progress_total = len(to_fetch)
        cls.progress_current = 0

        def _fetch_one(ticker: str):
            try:
                info = YahooFinanceService.safe_ticker_info(ticker)
                shares = info.get("sharesOutstanding")
                # Fallback: derive from marketCap / currentPrice
                if not shares:
                    cap = info.get("marketCap")
                    price = info.get("currentPrice") or info.get("regularMarketPrice")
                    if cap and price and price > 0:
                        shares = cap / price
                return ticker, float(shares) if shares else None
            except Exception as e:
                logger.debug("Failed to fetch shares for %s: %s", ticker, e)
                return ticker, None

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_fetch_one, t): t for t in to_fetch}
            for future in as_completed(futures):
                cls.progress_current += 1
                ticker, shares = future.result()
                if shares:
                    result[ticker] = shares

        # Persist
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(_SHARES_CACHE, "w") as f:
                json.dump(result, f)
        except Exception as e:
            logger.warning("Failed to save shares cache: %s", e)

        return result

    # ── Prices ────────────────────────────────────────────────────────────

    @classmethod
    def _fetch_prices(cls, tickers: List[str], now: float) -> "Optional[pd.DataFrame]":
        import pandas as pd

        # Try parquet cache
        if _PRICES_CACHE.exists():
            try:
                age = now - _PRICES_CACHE.stat().st_mtime
                if age < _PRICES_MAX_AGE:
                    df = pd.read_parquet(_PRICES_CACHE)
                    if not df.empty:
                        return df
            except Exception as e:
                logger.warning("Failed to load prices cache: %s", e)

        # Use the chunked batch helper — splits into groups of 200 so no
        # single subprocess exceeds the 120s timeout for period="max".
        try:
            from app.services.yahoo_finance_service import YahooFinanceService

            cls.progress_stage = f"Downloading price history ({len(tickers)} tickers)"
            cls.progress_current = 0
            cls.progress_total = len(tickers)

            def _progress(completed: int, total: int, _ticker: str):
                cls.progress_current = completed
                cls.progress_total = total

            results, failed = YahooFinanceService.fetch_batch_full_history(
                tickers, progress_callback=_progress
            )

            if not results:
                logger.error("Batch price fetch returned no results (failed=%d)", len(failed))
                return None

            cls.progress_stage = "Processing price data"

            # Build a wide Close DataFrame from the per-ticker OHLCV frames
            close_series = {}
            for ticker, ohlcv in results.items():
                if ohlcv is None or ohlcv.empty or "Close" not in ohlcv.columns:
                    continue
                s = ohlcv["Close"].dropna()
                if not s.empty:
                    close_series[ticker] = s

            if not close_series:
                logger.error("No Close price series extracted from batch results")
                return None

            close = pd.DataFrame(close_series)
            close.index = pd.DatetimeIndex(close.index)
            close = close.sort_index()
            close = close.dropna(axis=1, how="all")
            close = close.ffill()

            if failed:
                logger.info(
                    "Price fetch: %d tickers succeeded, %d failed",
                    len(close.columns), len(failed),
                )

            try:
                _CACHE_DIR.mkdir(parents=True, exist_ok=True)
                close.to_parquet(_PRICES_CACHE)
            except Exception as e:
                logger.warning("Failed to save prices cache: %s", e)

            return close
        except Exception as e:
            logger.error("Failed to fetch prices: %s", e)
            return None

    # ── Concentration math ────────────────────────────────────────────────

    @classmethod
    def _compute_concentration(
        cls, prices: "pd.DataFrame", shares: Dict[str, float]
    ) -> Optional[Dict]:
        import numpy as np
        import pandas as pd

        # Restrict to tickers we have shares for
        shared_tickers = [t for t in prices.columns if t in shares]
        if not shared_tickers:
            logger.error("No overlap between price columns and shares dict")
            return None

        prices = prices[shared_tickers].copy()
        shares_series = pd.Series({t: shares[t] for t in shared_tickers})

        # Market cap matrix: dates × tickers
        market_caps = prices.mul(shares_series, axis=1)
        market_caps = market_caps.dropna(how="all")

        # Drop rows where almost nothing is observed (early history with few tickers)
        non_null_count = market_caps.notna().sum(axis=1)
        min_required = max(1, int(len(shared_tickers) * 0.25))
        market_caps = market_caps[non_null_count >= min_required]
        if market_caps.empty:
            logger.error("Market cap matrix empty after filtering")
            return None

        # Weights matrix: each row sums to 1 (skipping NaNs)
        totals = market_caps.sum(axis=1, skipna=True)
        weights = market_caps.div(totals, axis=0).fillna(0.0)

        # Sorted weights (descending) per row → top MAX_N
        weights_arr = weights.values  # (n_dates, n_tickers)
        # Negate, sort ascending, slice → fastest descending sort
        sorted_arr = -np.sort(-weights_arr, axis=1)[:, :MAX_N]
        sorted_weights = pd.DataFrame(sorted_arr, index=weights.index)

        # HHI (×10000 to match standard convention)
        hhi = (weights_arr ** 2).sum(axis=1) * 10000.0
        hhi_series = pd.Series(hhi, index=weights.index)

        return {
            "sorted_weights": sorted_weights,
            "hhi": hhi_series,
            "ticker_count": len(shared_tickers),
            "as_of": pd.Timestamp.now(),
        }

    # ── Result cache ──────────────────────────────────────────────────────

    @classmethod
    def _load_result_cache(cls, now: float) -> Optional[Dict]:
        import pandas as pd

        if not _RESULT_CACHE.exists() or not _HHI_CACHE.exists():
            return None
        try:
            age = now - _RESULT_CACHE.stat().st_mtime
            if age > _RESULT_MAX_AGE:
                return None

            sorted_weights = pd.read_parquet(_RESULT_CACHE)
            sorted_weights.columns = list(range(len(sorted_weights.columns)))
            hhi_df = pd.read_parquet(_HHI_CACHE)

            # Tolerate legacy v1 hhi.parquet which also had an `effective_n`
            # column — we just read what we need.
            if "hhi" not in hhi_df.columns:
                return None

            return {
                "sorted_weights": sorted_weights,
                "hhi": hhi_df["hhi"],
                "ticker_count": int(hhi_df.attrs.get("ticker_count", 0)),
                "as_of": pd.Timestamp.now(),
            }
        except Exception as e:
            logger.warning("Failed to load result cache: %s", e)
            return None

    @classmethod
    def _save_result_cache(cls, result: Dict) -> None:
        import pandas as pd

        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            sorted_weights = result["sorted_weights"].copy()
            sorted_weights.columns = [str(c) for c in sorted_weights.columns]
            sorted_weights.to_parquet(_RESULT_CACHE)

            hhi_df = pd.DataFrame({"hhi": result["hhi"]})
            hhi_df.attrs["ticker_count"] = result.get("ticker_count", 0)
            hhi_df.to_parquet(_HHI_CACHE)

            # Clean up orphaned v1 files (top_n_returns.parquet from the
            # original 4-metric build, plus the un-versioned concentration
            # and hhi files from before MAX_N was bumped to 1000).
            for legacy in _LEGACY_FILES:
                if legacy.exists():
                    try:
                        legacy.unlink()
                    except OSError:
                        pass
        except Exception as e:
            logger.warning("Failed to save result cache: %s", e)
