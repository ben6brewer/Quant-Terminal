"""FakeYahoo - deterministic, offline stand-in for yfinance downloads.

* Prices are seeded by ``zlib.crc32(ticker)``; equities/ETFs are geometric
  random walks on NYSE-like weekdays (Jan 1 / Jul 4 / Dec 25 removed),
  ``-USD`` crypto trades 7 days a week, ``^`` indices/rates and ``=F`` /
  ``ZQ`` futures get realistic levels (``^IRX`` ~ 2.5, ``^VIX`` ~ 19,
  ``^MOVE`` ~ 100, ``ZQ*`` ~ 95.8 = 100 - rate).
* ``Adj Close`` differs from ``Close`` by a quarterly dividend drift for
  equities/ETFs (0.5-3 % yield), equal for indices, futures and crypto.
* Data ends at ``controller.as_of`` (default 2026-06-30).  ``start`` is
  inclusive, ``end`` exclusive, ``period`` ("1d","5d","1mo","3mo","6mo",
  "1y","2y","5y","10y","ytd","max"; default "1mo") is relative to ``as_of``.
* Output layout mimics yfinance 1.x ``download``: MultiIndex columns
  ``(Price, Ticker)`` (``group_by="column"``, the default - also for a single
  ticker unless ``multi_level_index=False``) or ``(Ticker, Price)`` for
  ``group_by="ticker"``; ``auto_adjust=True`` (yfinance default) adjusts OHLC
  and drops ``Adj Close``; index is a naive DatetimeIndex named ``Date``.

Patch with :func:`patch_yahoo` or the root-conftest ``fake_yahoo`` fixture::

    def test_x(fake_yahoo):                      # FakeYahooController
        fake_yahoo.missing.add("BADTICKER")
        df = YahooFinanceService.fetch_full_history("AAPL")
        assert fake_yahoo.calls[-1]["tickers"] == ["AAPL"]
"""

from __future__ import annotations

import re
import sys
import threading
import zlib
from functools import lru_cache
from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd

AS_OF = pd.Timestamp("2026-06-30")
PRICE_FIELDS_RAW = ["Adj Close", "Close", "High", "Low", "Open", "Volume"]  # yfinance column order (auto_adjust=False)
PRICE_FIELDS_ADJ = ["Close", "High", "Low", "Open", "Volume"]  # auto_adjust=True

# ticker -> ("rate", mean, sd, floor, cap) or ("level", end_price, drift, vol)
SPECIAL: Dict[str, tuple] = {
    "^IRX": ("rate", 2.5, 1.8, 0.01, None),
    "^FVX": ("rate", 3.0, 1.5, 0.05, None),
    "^TNX": ("rate", 3.8, 1.3, 0.3, None),
    "^TYX": ("rate", 4.1, 1.2, 0.8, None),
    "^VIX": ("rate", 19.0, 7.0, 9.0, None),
    "^MOVE": ("rate", 100.0, 25.0, 45.0, None),
    "^GSPC": ("level", 6200.0, 0.08, 0.18),
    "^SPX": ("level", 6200.0, 0.08, 0.18),
    "^DJI": ("level", 44000.0, 0.07, 0.17),
    "^IXIC": ("level", 20000.0, 0.10, 0.24),
    "^NDX": ("level", 22500.0, 0.11, 0.25),
    "^RUT": ("level", 2250.0, 0.07, 0.22),
    "^BXM": ("level", 4800.0, 0.06, 0.12),
    "BTC-USD": ("level", 105000.0, 0.45, 0.70),
    "ETH-USD": ("level", 3500.0, 0.40, 0.80),
    "GC=F": ("level", 2400.0, 0.06, 0.16),
    "SI=F": ("level", 30.0, 0.04, 0.28),
    "HG=F": ("level", 4.6, 0.04, 0.24),
    "PL=F": ("level", 1000.0, 0.01, 0.25),
    "PA=F": ("level", 1000.0, 0.03, 0.35),
    "CL=F": ("rate", 70.0, 20.0, 15.0, None),
}


# First trading day for well-known tickers (others: 1993-01-29 + crc-derived offset)
KNOWN_STARTS: Dict[str, str] = {
    "SPY": "1993-01-29", "QQQ": "1999-03-10", "IWM": "2000-05-26", "DIA": "1998-01-20",
    "MDY": "1995-05-04", "SPSM": "2013-07-08", "AGG": "2003-09-29", "TLT": "2002-07-30",
    "IEF": "2002-07-30", "SHY": "2002-07-30", "BIL": "2007-05-30", "TIP": "2003-12-05",
    "LQD": "2002-07-30", "HYG": "2007-04-11", "GLD": "2004-11-18", "SLV": "2006-04-28",
    "DJP": "2006-10-25", "VNQ": "2004-09-29", "EFA": "2001-08-17", "EEM": "2003-04-14",
    "VTI": "2001-06-15", "VOO": "2010-09-09", "AAPL": "1980-12-12", "MSFT": "1986-03-13",
    "AMZN": "1997-05-15", "GOOGL": "2004-08-19", "GOOG": "2014-03-27", "NVDA": "1999-01-22",
    "META": "2012-05-18", "TSLA": "2010-06-29", "BRK-B": "1996-05-09", "JPM": "1980-03-17",
    "XOM": "1980-03-17", "JNJ": "1980-03-17", "V": "2008-03-19", "UNH": "1984-10-17",
}


def asset_class(ticker: str) -> str:
    t = ticker.upper()
    if t.endswith("-USD"):
        return "crypto"
    if t.startswith("^"):
        return "index"
    if t.endswith("=F") or t.startswith("ZQ"):
        return "future"
    return "equity"


def _seed(ticker: str) -> int:
    return zlib.crc32(ticker.upper().encode("utf-8"))


def trading_index(ticker: str, as_of: pd.Timestamp = AS_OF) -> pd.DatetimeIndex:
    """Daily bar dates for ``ticker`` up to and including ``as_of``."""
    kind = asset_class(ticker)
    seed = _seed(ticker)
    if kind == "crypto":
        start = pd.Timestamp("2014-09-17") if ticker.upper() == "BTC-USD" else pd.Timestamp("2017-11-09")
        return pd.date_range(start, as_of, freq="D", name="Date")
    if kind == "index":
        start = pd.Timestamp("1990-01-02")
    elif kind == "future":
        start = pd.Timestamp("2000-08-30") if not ticker.upper().startswith("ZQ") else as_of - pd.DateOffset(years=2)
    elif ticker.upper() in KNOWN_STARTS:
        start = pd.Timestamp(KNOWN_STARTS[ticker.upper()])
    else:
        start = pd.Timestamp("1993-01-29") + pd.DateOffset(years=seed % 15, days=seed % 90)
    idx = pd.bdate_range(start, as_of, name="Date")
    md = idx.strftime("%m-%d")
    return idx[~np.isin(md, ["01-01", "07-04", "12-25"])]


def _ex_div_dates(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """First bar on/after the 15th of Mar/Jun/Sep/Dec."""
    out = []
    for year in range(idx[0].year, idx[-1].year + 1):
        for month in (3, 6, 9, 12):
            pos = idx.searchsorted(pd.Timestamp(year, month, 15))
            if pos < len(idx) and idx[pos].month == month:
                out.append(idx[pos])
    return pd.DatetimeIndex(out)


@lru_cache(maxsize=256)
def _history_cached(ticker: str, as_of: pd.Timestamp) -> pd.DataFrame:
    ticker = ticker.upper()
    idx = trading_index(ticker, as_of)
    n = len(idx)
    rng = np.random.default_rng(_seed(ticker))
    kind = asset_class(ticker)
    prof = SPECIAL.get(ticker)
    if prof is None and ticker.startswith("ZQ"):
        prof = ("rate", 95.8, 0.4, 94.0, 100.0)
    if prof is None:
        end_price = 20.0 + (_seed(ticker) % 4800) / 10.0
        vol = 0.20 + (_seed(ticker) % 25) / 100.0
        prof = ("level", end_price, 0.08, vol)

    spy = 365 if kind == "crypto" else 252
    if prof[0] == "rate":
        _, mean, sd, floor, cap = prof
        phi = 0.5 ** (1.0 / (2.0 * spy))
        eps = rng.standard_normal(n)
        close = np.empty(n)
        x = mean + sd * eps[0]
        scale = sd * np.sqrt(1 - phi * phi)
        for i in range(n):
            if i:
                x = mean + phi * (x - mean) + scale * eps[i]
            close[i] = x
        if floor is not None:
            close = np.maximum(close, floor)
        if cap is not None:
            close = np.minimum(close, cap)
    else:
        _, end_price, drift, vol = prof
        steps = drift / spy + (vol / np.sqrt(spy)) * rng.standard_normal(n)
        logp = np.cumsum(steps)
        close = end_price * np.exp(logp - logp[-1])

    daily_vol = float(np.nanstd(np.diff(np.log(np.maximum(close, 1e-9))))) if n > 2 else 0.01
    gap = rng.normal(0.0, daily_vol / 3.0, n)
    open_ = np.concatenate([[close[0]], close[:-1]]) * (1.0 + gap)
    spread = np.abs(rng.normal(0.0, daily_vol / 2.0, n))
    high = np.maximum(open_, close) * (1.0 + spread)
    low = np.minimum(open_, close) * (1.0 - spread)
    if kind == "index" and prof[0] == "rate":
        volume = np.zeros(n, dtype="int64")
    else:
        volume = rng.lognormal(mean=14.0 + (_seed(ticker) % 4), sigma=0.4, size=n).astype("int64")

    close = np.round(close, 6)
    adj = close.copy()
    if kind == "equity" and n:
        q = (0.5 + (_seed(ticker) % 26) / 10.0) / 100.0  # 0.5% .. 3.0% annual yield
        exd = _ex_div_dates(idx)
        # events strictly after each bar -> cumulative adjustment factor
        after = len(exd) - np.searchsorted(exd.values, idx.values, side="right")
        adj = np.round(close * (1.0 - q / 4.0) ** after, 6)

    return pd.DataFrame(
        {
            "Open": np.round(open_, 6),
            "High": np.round(high, 6),
            "Low": np.round(low, 6),
            "Close": close,
            "Adj Close": adj,
            "Volume": volume,
        },
        index=idx,
    )


def generate_history(ticker: str, as_of=AS_OF) -> pd.DataFrame:
    """Full deterministic daily history (Open, High, Low, Close, Adj Close, Volume)."""
    return _history_cached(ticker.upper(), pd.Timestamp(as_of)).copy()


def _parse_tickers(tickers) -> List[str]:
    if isinstance(tickers, str):
        parts = re.split(r"[\s,]+", tickers.strip())
    else:
        parts = list(tickers)
    out: List[str] = []
    for p in parts:
        p = str(p).strip().upper()
        if p and p not in out:
            out.append(p)
    return out


_PERIOD_RE = re.compile(r"^(\d+)(d|wk|mo|y)$")


def period_start(period: str, as_of: pd.Timestamp, index: pd.DatetimeIndex) -> Optional[pd.Timestamp]:
    """First bar date covered by a yfinance ``period`` string (None = all)."""
    if period in (None, "max"):
        return None
    if period == "ytd":
        return pd.Timestamp(as_of.year, 1, 1)
    m = _PERIOD_RE.match(period)
    if not m:
        raise ValueError(f"FakeYahoo: invalid period {period!r}")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return index[-n] if len(index) >= n else None
    if unit == "wk":
        return as_of - pd.DateOffset(weeks=n)
    if unit == "mo":
        return as_of - pd.DateOffset(months=n)
    return as_of - pd.DateOffset(years=n)


class FakeYahooController:
    """Shared state/recorder for a FakeYahoo patch.

    Attributes:
        as_of: last bar date (default 2026-06-30).
        calls: list of dicts ``{tickers, start, end, period, interval, auto_adjust, group_by}``.
        info_calls: tickers passed to ``safe_ticker_info``.
        missing: tickers that return no data (and ``{"trailingPegRatio": None}`` info).
        fail: tickers that make the whole download raise ``RuntimeError``.
        overrides: ``{ticker: DataFrame}`` full history served instead of generated
            (columns Open/High/Low/Close/Adj Close/Volume; sliced like generated data).
        info_overrides: ``{ticker: dict}`` returned by ``ticker_info``.
    """

    def __init__(self, as_of=AS_OF):
        self.as_of = pd.Timestamp(as_of)
        self.calls: List[dict] = []
        self.info_calls: List[str] = []
        self.missing: Set[str] = set()
        self.fail: Set[str] = set()
        self.overrides: Dict[str, pd.DataFrame] = {}
        self.info_overrides: Dict[str, dict] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def history(self, ticker: str, start=None, end=None, period=None) -> pd.DataFrame:
        """Flat single-ticker frame (Open, High, Low, Close, Adj Close, Volume)."""
        t = ticker.upper()
        if t in self.missing:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Adj Close", "Volume"])
        if t in self.overrides:
            df = self.overrides[t].copy()
            df.index = pd.DatetimeIndex(df.index, name="Date")
            df = df[df.index <= self.as_of]
        else:
            df = generate_history(t, self.as_of)
        if start is None and end is None and period is None:
            period = "1mo"
        if start is not None or end is not None:
            if start is not None:
                df = df[df.index >= pd.Timestamp(start)]
            if end is not None:
                df = df[df.index < pd.Timestamp(end)]
        elif period is not None and len(df):
            ps = period_start(period, self.as_of, df.index)
            if ps is not None:
                df = df[df.index >= ps]
        return df

    def download(self, tickers=None, start=None, end=None, period=None, interval="1d",
                 auto_adjust=True, group_by="column", multi_level_index=True, **_ignored) -> pd.DataFrame:
        """yfinance.download look-alike."""
        names = _parse_tickers(tickers if tickers is not None else [])
        with self._lock:
            self.calls.append({
                "tickers": names, "start": None if start is None else str(start),
                "end": None if end is None else str(end), "period": period,
                "interval": interval, "auto_adjust": auto_adjust, "group_by": group_by,
            })
        bad = [t for t in names if t in self.fail]
        if bad:
            raise RuntimeError(f"yf.download subprocess failed: FakeYahoo failure for {bad}")
        if interval not in ("1d", "1wk", "1mo"):
            raise NotImplementedError(f"FakeYahoo supports daily/weekly/monthly bars only, got {interval!r}")

        frames: Dict[str, pd.DataFrame] = {}
        for t in names:
            df = self.history(t, start=start, end=end, period=period)
            if df.empty:
                continue
            if interval != "1d":
                rule = "W-FRI" if interval == "1wk" else "MS"
                df = df.resample(rule).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last",
                                            "Adj Close": "last", "Volume": "sum"}).dropna(subset=["Close"])
            if auto_adjust:
                factor = df["Adj Close"] / df["Close"]
                df = df.assign(Open=df["Open"] * factor, High=df["High"] * factor,
                               Low=df["Low"] * factor, Close=df["Adj Close"]).drop(columns="Adj Close")
            frames[t] = df
        if not frames:
            return pd.DataFrame()

        index = pd.DatetimeIndex(sorted(set().union(*[f.index for f in frames.values()])), name="Date")
        per_ticker_fields = ["Open", "High", "Low", "Close"] + ([] if auto_adjust else ["Adj Close"]) + ["Volume"]
        parts = {}
        for t in sorted(names):
            if t in frames:
                parts[t] = frames[t][per_ticker_fields].reindex(index)
            else:  # yfinance keeps failed tickers as all-NaN columns
                parts[t] = pd.DataFrame(np.nan, index=index, columns=per_ticker_fields)
        out = pd.concat(parts, axis=1, names=["Ticker", "Price"])
        if group_by != "ticker":
            out = out.swaplevel(0, 1, axis=1).sort_index(axis=1, level=[0, 1])
            out.columns = out.columns.set_names(["Price", "Ticker"])
        if not multi_level_index and len(names) == 1:
            out.columns = out.columns.get_level_values("Price")
        out.index.name = "Date"
        return out

    def ticker_info(self, ticker: str) -> dict:
        t = ticker.upper()
        with self._lock:
            self.info_calls.append(t)
        if t in self.fail:
            raise RuntimeError(f"yf.Ticker().info subprocess failed: FakeYahoo failure for {t}")
        if t in self.info_overrides:
            return dict(self.info_overrides[t])
        if t in self.missing:
            return {"trailingPegRatio": None}
        seed = _seed(t)
        kind = asset_class(t)
        last = self.history(t, period="5d")
        price = float(last["Close"].iloc[-1]) if len(last) else None
        shares = 50_000_000 + (seed % 9_950) * 1_000_000
        sectors = ["Technology", "Healthcare", "Financial Services", "Consumer Cyclical", "Industrials",
                   "Energy", "Utilities", "Real Estate", "Basic Materials", "Communication Services",
                   "Consumer Defensive"]
        quote_type = {"crypto": "CRYPTOCURRENCY", "index": "INDEX", "future": "FUTURE"}.get(kind, "EQUITY")
        info = {
            "symbol": t,
            "shortName": f"{t} Fake Inc.",
            "longName": f"{t} Fake Incorporated",
            "quoteType": quote_type,
            "currency": "USD",
            "exchange": "NMS",
            "regularMarketPrice": price,
            "country": "United States",
        }
        if quote_type == "EQUITY":
            info.update({
                "sector": sectors[seed % len(sectors)],
                "industry": f"Fake Industry {seed % 40}",
                "beta": round(0.4 + (seed % 160) / 100.0, 2),
                "sharesOutstanding": shares,
                "marketCap": int(shares * price) if price else None,
                "trailingPE": round(8 + (seed % 400) / 10.0, 2),
                "priceToBook": round(0.8 + (seed % 120) / 10.0, 2),
                "returnOnEquity": round(((seed % 60) - 10) / 100.0, 4),
                "debtToEquity": round((seed % 250) * 1.0, 2),
                "revenueGrowth": round(((seed % 40) - 10) / 100.0, 4),
                "earningsGrowth": round(((seed % 60) - 20) / 100.0, 4),
                "fiftyTwoWeekChange": round(((seed % 80) - 30) / 100.0, 4),
                "dividendYield": round(0.5 + (seed % 26) / 10.0, 2),
            })
        return info


def patch_yahoo(monkeypatch, controller: Optional[FakeYahooController] = None,
                patch_yfinance: bool = True) -> FakeYahooController:
    """Serve ``YahooFinanceService.safe_download`` / ``safe_ticker_info`` (the
    only app entry points to yfinance) from FakeYahoo; also patch
    ``yfinance.download`` / ``yfinance.Ticker`` when yfinance is importable."""
    from app.services.yahoo_finance_service import YahooFinanceService

    ctl = controller or FakeYahooController()

    def fake_safe_download(cls, *args, **kwargs):
        if args and "tickers" not in kwargs:
            kwargs["tickers"] = args[0]
        return ctl.download(**kwargs)

    def fake_safe_ticker_info(cls, ticker, *args, **kwargs):
        return ctl.ticker_info(ticker)

    monkeypatch.setattr(YahooFinanceService, "safe_download", classmethod(fake_safe_download))
    monkeypatch.setattr(YahooFinanceService, "safe_ticker_info", classmethod(fake_safe_ticker_info))

    if patch_yfinance:
        try:
            import yfinance
        except Exception:  # pragma: no cover - yfinance is a runtime dependency
            yfinance = None
        if yfinance is not None:
            class _FakeTicker:
                def __init__(self, ticker, *a, **k):
                    self.ticker = str(ticker).upper()

                @property
                def info(self):
                    return ctl.ticker_info(self.ticker)

                def history(self, period="1mo", start=None, end=None, interval="1d", auto_adjust=True, **_):
                    df = ctl.download(self.ticker, start=start, end=end, period=period, interval=interval,
                                      auto_adjust=auto_adjust, multi_level_index=False)
                    return df

            def fake_download(tickers=None, *a, **kw):
                return ctl.download(tickers, *a, **kw)

            fake_download.__module__ = __name__
            _FakeTicker.__module__ = __name__
            monkeypatch.setattr(yfinance, "download", fake_download)
            monkeypatch.setattr(yfinance, "Ticker", _FakeTicker)
    return ctl
