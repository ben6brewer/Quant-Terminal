"""Stock Heatmap Service — Multi-market constituent fetch + yfinance price data."""

from __future__ import annotations

import io
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    import pandas as pd

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache"
_LOGO_DIR = _CACHE_DIR / "logos"

_CONSTITUENTS_MAX_AGE = 7 * 86400  # 7 days
_PRICE_MAX_AGE = 86400  # 1 day

MARKETS = ["S&P 500", "Nasdaq 100", "Dow 30"]

logger = logging.getLogger(__name__)


class SP500HeatmapService:
    """Fetches market constituents, market caps, and price history."""

    # Per-market in-memory cache
    _cache: Dict[str, Dict] = {}
    _cache_times: Dict[str, float] = {}

    # Progress tracking — read from main thread via QTimer polling
    progress_stage: str = ""
    progress_current: int = 0
    progress_total: int = 0

    @classmethod
    def fetch_all_data(cls, market: str = "S&P 500") -> Optional[Dict]:
        import pandas as pd

        now = time.time()

        # In-memory cache per market
        if market in cls._cache and market in cls._cache_times:
            if now - cls._cache_times[market] < _PRICE_MAX_AGE:
                return cls._cache[market]

        # Fetch constituents
        cls.progress_stage = f"Fetching {market} constituent list"
        cls.progress_current = 0
        cls.progress_total = 0

        info_df = cls._fetch_constituents(market)
        if info_df is None or info_df.empty:
            logger.error("Failed to fetch %s constituents", market)
            return None

        tickers = info_df["ticker"].tolist()

        # Fetch market caps
        cls.progress_stage = "Fetching market caps"
        cls.progress_total = len(tickers)
        market_caps = cls._fetch_market_caps(tickers)
        info_df["market_cap"] = info_df["ticker"].map(market_caps).fillna(0)

        # Fetch logos
        cls.progress_stage = "Fetching logos"
        logo_paths = cls._fetch_logos(tickers)

        # Fetch price data
        cache_file = _CACHE_DIR / f"heatmap_{market.lower().replace(' ', '_')}_prices.parquet"
        price_data = cls._load_price_cache(cache_file, now)
        if price_data is None:
            cls.progress_stage = "Downloading price data..."
            cls.progress_current = 0
            cls.progress_total = 0
            price_data = cls._fetch_price_data(tickers)
            if price_data is not None and not price_data.empty:
                cls.progress_stage = "Saving price cache..."
                cls._save_price_cache(price_data, cache_file)

        if price_data is None or price_data.empty:
            logger.error("Failed to fetch %s price data", market)
            return None

        result = {
            "sp500_info": info_df,
            "price_data": price_data,
            "logo_paths": logo_paths,
        }
        cls._cache[market] = result
        cls._cache_times[market] = now
        return result

    # ── Constituent fetchers ──────────────────────────────────────────────

    @classmethod
    def _fetch_constituents(cls, market: str) -> "Optional[pd.DataFrame]":
        if market == "S&P 500":
            return cls._scrape_wikipedia(
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                "sp500",
                {"Symbol": "ticker", "Security": "name",
                 "GICS Sector": "sector", "GICS Sub-Industry": "sub_industry"},
                table_index=0,
            )
        if market == "Nasdaq 100":
            return cls._scrape_wikipedia(
                "https://en.wikipedia.org/wiki/Nasdaq-100",
                "nasdaq100",
                {"Ticker": "ticker", "Company": "name",
                 "ICB Industry": "sector", "ICB Subsector": "sub_industry"},
                table_index=4,
            )
        if market == "Dow 30":
            return cls._scrape_wikipedia(
                "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
                "dow30",
                {"Symbol": "ticker", "Company": "name", "Sector": "sector"},
                table_index=1,
            )
        return None

    @classmethod
    def _scrape_wikipedia(cls, url: str, cache_key: str,
                          column_map: Dict[str, str],
                          table_index: int = 0) -> "Optional[pd.DataFrame]":
        import pandas as pd
        import requests

        cache_file = _CACHE_DIR / f"heatmap_{cache_key}.json"

        # Check cache
        if cache_file.exists():
            try:
                age = time.time() - cache_file.stat().st_mtime
                if age < _CONSTITUENTS_MAX_AGE:
                    df = pd.read_json(cache_file)
                    if not df.empty:
                        return df
            except Exception as e:
                logger.warning("Failed to load %s cache: %s", cache_key, e)

        try:
            resp = requests.get(url, headers={"User-Agent": "QuantTerminal/1.0"}, timeout=30)
            resp.raise_for_status()
            tables = pd.read_html(io.StringIO(resp.text))
            df = tables[table_index]

            # Strip Wikipedia footnote references like [14] from column names
            df.columns = [re.sub(r"\[.*?\]", "", str(c)).strip() for c in df.columns]

            # Rename columns that exist
            rename = {k: v for k, v in column_map.items() if k in df.columns}
            df = df.rename(columns=rename)

            # Ensure required columns exist
            if "ticker" not in df.columns:
                df = df.rename(columns={df.columns[0]: "ticker"})
            if "name" not in df.columns:
                df["name"] = df["ticker"]
            if "sector" not in df.columns:
                df["sector"] = "Other"
            if "sub_industry" not in df.columns:
                df["sub_industry"] = ""

            df = df[["ticker", "name", "sector", "sub_industry"]].copy()
            df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)

            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_json(cache_file)
            logger.info("Cached %d %s constituents", len(df), cache_key)
            return df

        except Exception as e:
            logger.error("Failed to scrape %s: %s", cache_key, e)
            if cache_file.exists():
                try:
                    return pd.read_json(cache_file)
                except Exception:
                    pass
            return None

    # ── Market caps ───────────────────────────────────────────────────────

    @classmethod
    def _fetch_market_caps(cls, tickers: List[str]) -> Dict[str, float]:
        from app.services.ticker_metadata_service import TickerMetadataService

        try:
            cls.progress_current = 0
            cls.progress_total = len(tickers)

            metadata = TickerMetadataService.get_metadata_batch(tickers, max_workers=10)
            cls.progress_current = len(tickers)

            caps = {}
            for ticker, meta in metadata.items():
                cap = meta.get("marketCap")
                if cap and cap > 0:
                    caps[ticker] = float(cap)
            return caps
        except Exception as e:
            logger.error("Failed to fetch market caps: %s", e)
            return {}

    # ── Logo fetching ─────────────────────────────────────────────────────

    @classmethod
    def _fetch_logos(cls, tickers: List[str]) -> Dict[str, str]:
        """Fetch SVG logos from Parqet by ticker symbol. Cache as .svg files."""
        _LOGO_DIR.mkdir(parents=True, exist_ok=True)

        logo_paths: Dict[str, str] = {}
        to_fetch: List[str] = []

        for ticker in tickers:
            safe_name = ticker.replace("/", "_")
            logo_file = _LOGO_DIR / f"{safe_name}.svg"
            if logo_file.exists() and logo_file.stat().st_size > 0:
                logo_paths[ticker] = str(logo_file)
                continue
            to_fetch.append(ticker)

        if not to_fetch:
            return logo_paths

        cls.progress_current = 0
        cls.progress_total = len(to_fetch)

        def _download_one(ticker: str):
            try:
                import requests
                safe_name = ticker.replace("/", "_")
                url = f"https://assets.parqet.com/logos/symbol/{ticker}"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200 and len(resp.content) > 50:
                    logo_file = _LOGO_DIR / f"{safe_name}.svg"
                    logo_file.write_bytes(resp.content)
                    return ticker, str(logo_file)
            except Exception:
                pass
            return ticker, None

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = {pool.submit(_download_one, t): t for t in to_fetch}
            for future in as_completed(futures):
                cls.progress_current += 1
                ticker, path = future.result()
                if path:
                    logo_paths[ticker] = path

        return logo_paths

    # ── Price data ────────────────────────────────────────────────────────

    @classmethod
    def _fetch_price_data(cls, tickers: List[str]) -> "Optional[pd.DataFrame]":
        import pandas as pd

        try:
            from app.services.yahoo_finance_service import YahooFinanceService

            logger.info("Fetching price data for %d tickers...", len(tickers))
            cls.progress_stage = f"Downloading prices for {len(tickers)} tickers..."
            raw = YahooFinanceService.safe_download(
                tickers, period="1y", progress=False, threads=False
            )

            if raw is None or raw.empty:
                return None

            cls.progress_stage = "Processing price data..."

            if isinstance(raw.columns, pd.MultiIndex):
                close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else None
                if close is None:
                    return None
            else:
                close = raw[["Close"]].rename(columns={"Close": tickers[0]})

            close.index = pd.DatetimeIndex(close.index)
            close = close.ffill()
            close = close.dropna(axis=1, how="all")

            logger.info("Fetched price data for %d tickers", len(close.columns))
            return close

        except Exception as e:
            logger.error("Failed to fetch prices: %s", e)
            return None

    @classmethod
    def _load_price_cache(cls, cache_file: Path, now: float) -> "Optional[pd.DataFrame]":
        import pandas as pd

        if not cache_file.exists():
            return None
        try:
            age = now - cache_file.stat().st_mtime
            if age > _PRICE_MAX_AGE:
                return None
            df = pd.read_parquet(cache_file)
            return df if not df.empty else None
        except Exception as e:
            logger.warning("Failed to load price cache: %s", e)
            return None

    @classmethod
    def _save_price_cache(cls, df: "pd.DataFrame", cache_file: Path):
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache_file)
        except Exception as e:
            logger.warning("Failed to save price cache: %s", e)
