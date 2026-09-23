"""Characterization of the price cascade: memory -> disk (parquet) -> Yahoo.

Covers the three public OHLCV entry points of ``app.services.market_data``
(``fetch_price_history``, ``fetch_price_history_yahoo`` and
``fetch_price_history_batch``), ``MarketDataCache`` (parquet cache plus the
NYSE/crypto staleness rule) and ``YahooFinanceService`` (the only yfinance
gateway), all served offline by FakeYahoo (``tests/fixtures/fake_yahoo.py``)
inside a per-test ``fresh_home``.

What is pinned, and how:

* Outputs, the Yahoo call log and the on-disk cache state are golden files in
  ``tests/goldens/market_data/``.  They must stay identical through pure
  refactors (P2 B-cache, P7.0 pure commits); only a ``Behavior-Change: yes``
  commit may regenerate them.
* Parquet reads are counted by wrapping ``pandas.read_parquet``.  The passing
  tests assert today's counts as budgets (``<=``) so a fix that removes reads
  stays green, while the target counts are strict xfails
  (``KNOWN-BUG:md-parquet-reread``) that XPASS, and therefore fail, as soon as
  the P2 fix lands.  The fixing phase then removes the marker.
* Freshness depends on ``datetime.now()`` inside ``market_data_cache`` and
  ``utils.market_hours``.  ``FrozenClock`` pins both to an America/New_York
  instant (default 2026-06-30 18:00, a Tuesday after the close, which is also
  FakeYahoo's last bar), so caches ending 2026-06-30 are current.
* Known bugs are strict xfails whose reason starts with ``KNOWN-BUG:<id>``:
  ``md-parquet-reread``, ``md-version-recheck``, ``md-version-entrypoints``,
  ``md-btc-chart-no-prepend`` and ``md-period-ignored``.

Explicit assertions pin only behavior that is meant to survive the refactor.
Behavior that is known to be wrong is recorded in goldens only, so the phase
that fixes it regenerates them in a behavior commit instead of editing
assertions here.
"""

from __future__ import annotations

import datetime as _dt
import importlib
import re
import zlib
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from fixtures.fake_yahoo import generate_history, trading_index
from golden_utils import assert_golden, frame_digest

pytestmark = pytest.mark.golden

AREA = "market_data"
NY = ZoneInfo("America/New_York")
AS_OF = pd.Timestamp("2026-06-30")  # FakeYahoo's last bar
AFTER_CLOSE = "2026-06-30 18:00"  # Tue after the NYSE close: caches ending 06-30 are current
DAY1 = "2026-06-15"  # "yesterday's session" for two-day scenarios (a Monday)
DAY1_AFTER_CLOSE = "2026-06-15 18:00"
OHLCV = ["Open", "High", "Low", "Close", "Volume"]

CUSTOM_DAILY = "_QT_TEST_series"
CUSTOM_MONTHLY = "_QT_TEST_monthly"
NODATA = "_QT_TEST_NODATA"  # FakeYahoo returns no rows for it
FAILING = "_QT_TEST_FAIL"  # FakeYahoo raises for any download that includes it
BTC_CSV_FIRST = pd.Timestamp("2012-01-01")


# ─────────────────────────────────────────────────────────────────────────────
# Harness
# ─────────────────────────────────────────────────────────────────────────────


class FrozenClock:
    """Freeze ``datetime.now()`` in the modules that decide cache freshness.

    ``now(tz)`` returns the frozen New York instant converted to ``tz``, and
    ``now()`` returns its naive New York wall-clock time (the crypto rule in
    ``MarketDataCache.is_cache_current`` compares against it).
    ``_perform_yahoo_incremental_update`` imports ``datetime`` inside the
    function, so its ``end`` argument follows the real clock.  The harness
    normalizes that value (see ``Harness.calls_since``).
    """

    MODULES = ("app.services.market_data_cache", "app.utils.market_hours")

    def __init__(self, monkeypatch, when: str = AFTER_CLOSE):
        clock = self

        class _FrozenDateTime(_dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return clock._now.replace(tzinfo=None) if tz is None else clock._now.astimezone(tz)

        for name in self.MODULES:
            mod = importlib.import_module(name)
            assert getattr(mod, "datetime", None) is _dt.datetime, (
                f"{name}.datetime is no longer datetime.datetime; update FrozenClock.MODULES"
            )
            monkeypatch.setattr(mod, "datetime", _FrozenDateTime)
        self._now = None
        self.set(when)

    def set(self, when: str) -> None:
        self._now = pd.Timestamp(when).to_pydatetime().replace(tzinfo=NY)


class ParquetSpy:
    """Count ``pandas.read_parquet`` calls, labelled relative to ``~/.quant_terminal``."""

    def __init__(self, monkeypatch, root: Path):
        self.root = root
        self.reads: list = []
        self.real = pd.read_parquet

        def _counting_read_parquet(path, *args, **kwargs):
            self.reads.append(self._label(path))
            return self.real(path, *args, **kwargs)

        monkeypatch.setattr(pd, "read_parquet", _counting_read_parquet)

    def _label(self, path) -> str:
        try:
            return Path(path).resolve().relative_to(self.root).as_posix()
        except (TypeError, ValueError):
            return str(path)


class Harness:
    def __init__(self, md, cache_cls, yahoo_cls, fake, home: Path, clock: FrozenClock, spy: ParquetSpy):
        self.md = md
        self.cache_cls = cache_cls
        self.yahoo = yahoo_cls
        self.fake = fake
        self.home = home
        self.clock = clock
        self.spy = spy

    # paths ------------------------------------------------------------------
    @property
    def cache_dir(self) -> Path:
        return Path(self.cache_cls._CACHE_DIR)

    @property
    def version_file(self) -> Path:
        return self.cache_dir / ".data_source_version"

    @property
    def current_version(self) -> str:
        return self.md._DATA_SOURCE_VERSION

    # state helpers ----------------------------------------------------------
    def prime_version(self) -> None:
        """Write the current data-source version, as any earlier session would have.
        Without it the first fetch_price_history call wipes every seeded parquet."""
        self.version_file.write_text(self.current_version)

    def drop_memory(self) -> None:
        """Simulate an app restart: forget the in-process price and live-bar caches."""
        for name in ("_memory_cache", "_live_bar_cache"):
            store = getattr(self.md, name, None)
            assert isinstance(store, dict), f"market_data.{name} moved; update Harness.drop_memory"
            store.clear()

    def history(self, ticker: str, end=AS_OF) -> pd.DataFrame:
        """FakeYahoo history through ``end`` (inclusive), in the app's OHLCV layout."""
        full = generate_history(ticker)
        return full.loc[: pd.Timestamp(end), OHLCV]

    def seed_disk(self, ticker: str, end=AS_OF, close_scale: float = 1.0) -> pd.DataFrame:
        """Write a parquet cache file through the public MarketDataCache API."""
        df = self.history(ticker, end)
        if close_scale != 1.0:
            df = df.assign(**{c: df[c] * close_scale for c in ("Open", "High", "Low", "Close")})
        self.cache_cls().save_to_cache(ticker, df)
        return df

    def seed_custom(self) -> None:
        from app.services import custom_data_service as cds

        rng = np.random.default_rng(zlib.crc32(CUSTOM_DAILY.encode()))
        idx = pd.bdate_range("2025-01-02", "2025-12-31")
        cds.save_custom_import(CUSTOM_DAILY, pd.Series(rng.normal(0.0004, 0.01, len(idx)), index=idx),
                               "daily", "Equity", f"{CUSTOM_DAILY}.csv")
        rng = np.random.default_rng(zlib.crc32(CUSTOM_MONTHLY.encode()))
        idx = pd.date_range("2020-01-31", "2025-12-31", freq="ME")
        cds.save_custom_import(CUSTOM_MONTHLY, pd.Series(rng.normal(0.006, 0.04, len(idx)), index=idx),
                               "monthly", "Fixed Income", f"{CUSTOM_MONTHLY}.csv")

    # recording --------------------------------------------------------------
    def mark(self) -> tuple:
        return (len(self.fake.calls), len(self.spy.reads), _dt.date.today())

    def calls_since(self, mark: tuple) -> list:
        """Yahoo download calls since ``mark``.  An ``end`` equal to the real
        today+1 (from ``_perform_yahoo_incremental_update``) becomes a token."""
        wall = {(mark[2] + _dt.timedelta(days=1)).isoformat(),
                (_dt.date.today() + _dt.timedelta(days=1)).isoformat()}
        out = []
        for call in self.fake.calls[mark[0]:]:
            call = dict(call)
            if call.get("end") in wall:
                call["end"] = "<wall-clock today+1>"
            out.append(call)
        return out

    def reads_since(self, mark: tuple) -> list:
        return self.spy.reads[mark[1]:]

    def info_calls(self) -> list:
        return sorted(set(self.fake.info_calls))

    def disk_state(self) -> dict:
        """Digest of every top-level parquet file plus the data-source version file."""
        files = {}
        for p in sorted(self.cache_dir.glob("*.parquet")):
            try:
                files[p.name] = frame_digest(self.spy.real(p))
            except Exception as exc:  # corrupt file: record, don't crash
                files[p.name] = f"unreadable: {type(exc).__name__}"
        version = self.version_file.read_text().strip() if self.version_file.exists() else None
        return {"parquet": files, "data_source_version": version}


@pytest.fixture
def h(fake_yahoo, fresh_home, monkeypatch):
    """Market-data harness: FakeYahoo, fresh home, frozen clock, parquet spy, clean memory."""
    from app.services import market_data as md
    from app.services.market_data_cache import MarketDataCache
    from app.services.ticker_metadata_service import TickerMetadataService
    from app.services.yahoo_finance_service import YahooFinanceService

    root = fresh_home / ".quant_terminal"
    assert Path(MarketDataCache._CACHE_DIR).resolve() == (root / "cache").resolve()
    # MarketDataCache() creates its directory at import time (session home);
    # recreate it in the fresh home like the app would have.
    MarketDataCache._CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Session-global in-memory state that must not leak between tests.
    for name, value in list(vars(md).items()):
        if "version_checked" in name and isinstance(value, bool):  # the P2 flag, if present
            monkeypatch.setattr(md, name, False)
    monkeypatch.setattr(TickerMetadataService, "_cache", None)

    harness = Harness(md, MarketDataCache, YahooFinanceService, fake_yahoo, fresh_home,
                      FrozenClock(monkeypatch), ParquetSpy(monkeypatch, root))
    harness.drop_memory()
    harness.prime_version()
    yield harness
    harness.drop_memory()


def _periods(calls: list) -> list:
    return [c["period"] for c in calls]


# ─────────────────────────────────────────────────────────────────────────────
# fetch_price_history
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_price_history_cascade(h):
    """Cold (Yahoo), then memory, then disk after a restart: same frame every time."""
    md = h.md
    m = h.mark()
    cold = md.fetch_price_history("aapl")
    cold_calls = h.calls_since(m)

    m = h.mark()
    memory = md.fetch_price_history("AAPL")
    memory_calls = h.calls_since(m)

    h.drop_memory()
    m = h.mark()
    disk = md.fetch_price_history(" AAPL ")
    disk_calls = h.calls_since(m)

    # cold: one full-history download plus the live-bar probe
    assert _periods(cold_calls) == ["max", "5d"]
    assert cold_calls[0]["tickers"] == ["AAPL"] and cold_calls[0]["auto_adjust"] is False
    assert memory_calls == []  # live bar is cached for 15 minutes too
    assert _periods(disk_calls) == ["5d"]  # history from parquet, live-bar probe only
    assert list(cold.columns) == OHLCV
    assert cold.index.max() == AS_OF
    assert cold.index.min() == trading_index("AAPL")[0]
    pd.testing.assert_frame_equal(memory, cold)
    pd.testing.assert_frame_equal(disk, cold)
    np.testing.assert_allclose(cold["Close"].to_numpy(), generate_history("AAPL")["Close"].to_numpy())

    period_1y = md.fetch_price_history("AAPL", period="1y", skip_live_bar=True)

    assert_golden("fph_cascade", {
        "result": frame_digest(cold),
        "calls": {"cold": cold_calls, "memory": memory_calls, "disk": disk_calls},
        "info_calls": h.info_calls(),
        "disk": h.disk_state(),
        # KNOWN-BUG:md-period-ignored - `period` is accepted but ignored today
        "period_1y_rows": len(period_1y),
    }, area=AREA)


def test_fetch_price_history_two_day_refresh(h):
    """A stale cache (same session) triggers a FULL re-download, not an incremental one."""
    md = h.md
    h.fake.overrides["AAPL"] = generate_history("AAPL").loc[:DAY1]  # Yahoo only has data through DAY1
    h.clock.set(DAY1_AFTER_CLOSE)
    day1 = md.fetch_price_history("AAPL", skip_live_bar=True)
    disk_day1 = h.disk_state()

    h.fake.overrides.pop("AAPL")  # a trading fortnight later Yahoo has data through AS_OF
    h.clock.set(AFTER_CLOSE)
    m = h.mark()
    day2 = md.fetch_price_history("AAPL", skip_live_bar=True)
    day2_calls = h.calls_since(m)

    assert day1.index.max() == pd.Timestamp(DAY1)
    assert day2.index.max() == AS_OF
    assert _periods(day2_calls) == ["max"]
    np.testing.assert_allclose(day2["Close"].to_numpy(), generate_history("AAPL")["Close"].to_numpy())

    assert_golden("fph_two_day_refresh", {
        "day1": frame_digest(day1),
        "day2": frame_digest(day2),
        "day2_calls": day2_calls,
        "disk_day1": disk_day1,
        "disk_day2": h.disk_state(),
    }, area=AREA)


def test_fetch_price_history_failure_paths(h):
    md = h.md

    # 1. Yahoo down + stale parquet -> the stale parquet is served (not an error)
    h.seed_disk("AAPL", end=DAY1)
    h.fake.fail.add("AAPL")
    m = h.mark()
    stale = md.fetch_price_history("AAPL")
    stale_calls = h.calls_since(m)
    assert stale.index.max() == pd.Timestamp(DAY1)
    assert _periods(stale_calls) == ["max", "5d"]  # both attempts raised inside the service

    # 2. no cache and no data -> ValueError(ERROR_NO_DATA)
    h.fake.missing.add(NODATA)
    with pytest.raises(ValueError, match=re.escape(f"No data returned for ticker '{NODATA}'.")):
        md.fetch_price_history(NODATA.lower(), skip_live_bar=True)
    assert not (h.cache_dir / f"{NODATA}.parquet").exists()

    # 3. blank ticker -> ValueError(ERROR_EMPTY_TICKER)
    with pytest.raises(ValueError, match=re.escape("Ticker is empty.")):
        md.fetch_price_history("   ")

    # 4. unreadable parquet -> treated as missing, re-downloaded and overwritten
    (h.cache_dir / "MSFT.parquet").write_bytes(b"_QT_TEST_ not a parquet file")
    m = h.mark()
    recovered = md.fetch_price_history("MSFT", skip_live_bar=True)
    recovered_calls = h.calls_since(m)
    assert _periods(recovered_calls) == ["max"]
    assert recovered.index.max() == AS_OF
    pd.testing.assert_frame_equal(h.spy.real(h.cache_dir / "MSFT.parquet"), recovered)

    assert_golden("fph_failure_paths", {
        "stale_fallback": frame_digest(stale),
        "stale_fallback_calls": stale_calls,
        "corrupt_recovered": frame_digest(recovered),
        "corrupt_recovered_calls": recovered_calls,
        "disk": h.disk_state(),
    }, area=AREA)


def test_intervals_both_single_ticker_paths(h):
    """Interval aliases resample identically on the two single-ticker paths."""
    md = h.md
    aliases = {
        "daily": ("daily", "1d", "Daily", "15m"),  # unknown intervals fall back to daily
        "weekly": ("weekly", "1wk", "Weekly"),
        "monthly": ("monthly", "1mo", "Monthly"),
        "yearly": ("yearly", "1y", "Yearly"),
    }
    canonical = {}
    for label, names in aliases.items():
        frames = []
        for iv in names:
            frames.append(md.fetch_price_history("AAPL", interval=iv, skip_live_bar=True))
            frames.append(md.fetch_price_history_yahoo("AAPL", interval=iv))
        for other in frames[1:]:
            pd.testing.assert_frame_equal(other, frames[0])
        canonical[label] = frames[0]

    daily, weekly = canonical["daily"], canonical["weekly"]
    assert len(daily) == len(trading_index("AAPL"))
    assert list(weekly.columns) == OHLCV
    assert weekly["Volume"].sum() == daily["Volume"].sum()
    assert weekly["High"].max() == daily["High"].max()
    assert canonical["yearly"].index.max() == pd.Timestamp("2026-12-31")  # period-end labels
    # exactly one Yahoo download for all 30 requests (memory served the rest)
    assert _periods(h.fake.calls) == ["max"]

    assert_golden("intervals", {k: frame_digest(v) for k, v in canonical.items()}, area=AREA)


def test_live_bar_append(h):
    """Before the close the cache is current through yesterday; today's partial bar is
    appended to the returned frame (not to the cache) unless skip_live_bar=True."""
    md = h.md
    h.seed_disk("AAPL", end="2026-06-29")
    h.clock.set("2026-06-30 12:00")  # market open: last expected trading date is 06-29

    m = h.mark()
    with_live = md.fetch_price_history("AAPL")
    first_calls = h.calls_since(m)
    m = h.mark()
    again = md.fetch_price_history("AAPL")
    second_calls = h.calls_since(m)
    no_live = md.fetch_price_history("AAPL", skip_live_bar=True)
    weekly = md.fetch_price_history("AAPL", interval="weekly")
    chart = md.fetch_price_history_yahoo("AAPL")

    assert _periods(first_calls) == ["5d"]  # cache is current: only the live-bar probe
    assert second_calls == []  # live bar reused within 15 minutes
    assert no_live.index.max() == pd.Timestamp("2026-06-29")
    assert with_live.index.max() == AS_OF and len(with_live) == len(no_live) + 1
    pd.testing.assert_frame_equal(with_live.iloc[:-1], no_live)
    pd.testing.assert_frame_equal(again, with_live)
    assert chart.index.max() == pd.Timestamp("2026-06-29")  # the chart path never appends
    assert weekly.index.max() == pd.Timestamp("2026-07-05")  # W-SUN label of the live week
    assert h.cache_cls().get_cached_data("AAPL").index.max() == pd.Timestamp("2026-06-29")

    assert_golden("live_bar", {
        "live_row": {k: float(v) for k, v in with_live.iloc[-1].items()},
        "with_live": frame_digest(with_live),
        "weekly_with_live": frame_digest(weekly.tail(3)),
        "calls": first_calls,
        "disk": h.disk_state(),
    }, area=AREA)


def test_btc_historical_prepend(h):
    """BTC-USD gets bitcoin_historical_prices.csv prepended before Yahoo's first bar."""
    from app.core.paths import services_dir

    md = h.md
    csv = pd.read_csv(services_dir() / "bitcoin_historical_prices.csv", parse_dates=["date"], index_col="date")
    yahoo_first = trading_index("BTC-USD")[0]
    csv_before = csv[csv.index < yahoo_first]

    single = md.fetch_price_history("BTC-USD", skip_live_bar=True)
    assert single.index.min() == BTC_CSV_FIRST == csv.index.min()
    assert single.index.is_unique and single.index.is_monotonic_increasing
    pre = single.loc[single.index < yahoo_first]
    assert len(pre) == len(csv_before)
    np.testing.assert_allclose(pre["Close"].to_numpy(), csv_before["close"].to_numpy())
    np.testing.assert_allclose(single.loc[yahoo_first:, "Close"].to_numpy(),
                               generate_history("BTC-USD")["Close"].to_numpy())
    disk_single = h.disk_state()

    md.clear_cache("BTC-USD")
    batch = md.fetch_price_history_batch(["BTC-USD", "SPY"])["BTC-USD"]
    assert batch.index.min() == BTC_CSV_FIRST
    np.testing.assert_allclose(batch["Close"].to_numpy(), single["Close"].to_numpy())

    # chart path (fresh fetch), then the portfolio path reading what the chart cached
    md.clear_cache("BTC-USD")
    chart = md.fetch_price_history_yahoo("BTC-USD")
    h.drop_memory()
    after_chart = md.fetch_price_history("BTC-USD", skip_live_bar=True)

    assert_golden("btc_prepend", {
        "csv_rows_before_yahoo": len(csv_before),
        "fetch_price_history": frame_digest(single),
        "batch": frame_digest(batch),
        "disk_after_fetch_price_history": disk_single,
        # KNOWN-BUG:md-btc-chart-no-prepend - no CSV history on the chart path, and it poisons the cache
        "chart_fresh": frame_digest(chart),
        "fetch_price_history_after_chart": frame_digest(after_chart),
    }, area=AREA)


# ─────────────────────────────────────────────────────────────────────────────
# Data-source version check
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", ["missing", "current", "outdated"])
def test_data_source_version_check(h, case):
    """fetch_price_history wipes the parquet cache unless the version file holds the
    current _DATA_SOURCE_VERSION ("yahoo_v2" at BASE)."""
    md = h.md
    if hasattr(md, "_VERSION_FILE"):
        assert Path(md._VERSION_FILE) == h.version_file
    h.seed_disk("SPY", close_scale=2.0)  # distinguishable "other provider" data, current
    pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.to_datetime(["2026-06-29", "2026-06-30"])).to_parquet(
        h.cache_dir / "metals_futures.parquet")  # another service's file in the same directory
    h.seed_custom()
    if case == "missing":
        h.version_file.unlink()
    elif case == "outdated":
        h.version_file.write_text("yahoo_v1")
    before = h.disk_state()

    m = h.mark()
    out = md.fetch_price_history("SPY", skip_live_bar=True)
    calls = h.calls_since(m)

    fake_close = generate_history("SPY")["Close"]
    assert h.version_file.read_text().strip() == h.current_version
    from app.services.custom_data_service import get_metadata
    assert get_metadata(CUSTOM_DAILY) is not None  # custom imports live outside cache/
    if case == "current":
        assert calls == []
        np.testing.assert_allclose(out["Close"].to_numpy(), 2.0 * fake_close.to_numpy())
    else:
        assert _periods(calls) == ["max"]
        np.testing.assert_allclose(out["Close"].to_numpy(), fake_close.to_numpy())

    assert_golden(f"version_check_{case}", {
        "before": before,
        "after": h.disk_state(),
        "calls": calls,
        "result": frame_digest(out),
    }, area=AREA)


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN-BUG:md-version-recheck - _check_data_source_version reads the version file on every "
    "fetch_price_history call; P2 B-cache adds a once-per-session flag"))
def test_version_checked_once_per_session(h):
    md = h.md
    md.fetch_price_history("SPY", skip_live_bar=True)
    h.version_file.write_text("yahoo_v1")  # changes after the session's first check
    m = h.mark()
    md.fetch_price_history("SPY", skip_live_bar=True)
    assert h.calls_since(m) == []  # today: wipes the cache and downloads SPY again


_VERSION_ENTRYPOINT_BUG = pytest.mark.xfail(strict=True, reason=(
    "KNOWN-BUG:md-version-entrypoints - only fetch_price_history runs _check_data_source_version; "
    "the chart and batch paths serve parquet written by an older data source"))


@pytest.mark.parametrize("entry", [
    "fetch_price_history",
    pytest.param("fetch_price_history_yahoo", marks=_VERSION_ENTRYPOINT_BUG),
    pytest.param("fetch_price_history_batch", marks=_VERSION_ENTRYPOINT_BUG),
])
def test_every_entry_point_enforces_data_source_version(h, entry):
    md = h.md
    h.seed_disk("SPY", close_scale=2.0)
    h.version_file.write_text("yahoo_v1")
    if entry == "fetch_price_history":
        out = md.fetch_price_history("SPY", skip_live_bar=True)
    elif entry == "fetch_price_history_yahoo":
        out = md.fetch_price_history_yahoo("SPY")
    else:
        out = md.fetch_price_history_batch(["SPY"])["SPY"]
    np.testing.assert_allclose(out["Close"].to_numpy(), generate_history("SPY")["Close"].to_numpy())
    assert h.version_file.read_text().strip() == h.current_version


# ─────────────────────────────────────────────────────────────────────────────
# fetch_price_history_yahoo (chart path)
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_price_history_yahoo_cascade(h):
    md = h.md

    # cold -> memory -> disk
    m = h.mark()
    cold = md.fetch_price_history_yahoo("aapl")
    cold_calls = h.calls_since(m)
    m = h.mark()
    memory = md.fetch_price_history_yahoo("AAPL")
    memory_calls = h.calls_since(m)
    h.drop_memory()
    m = h.mark()
    disk = md.fetch_price_history_yahoo("AAPL")
    disk_calls = h.calls_since(m)
    assert _periods(cold_calls) == ["max"]  # no live-bar probe on the chart path
    assert memory_calls == [] and disk_calls == []
    pd.testing.assert_frame_equal(memory, cold)
    pd.testing.assert_frame_equal(disk, cold)
    assert cold.index.max() == AS_OF

    # two-day: a stale cache is updated INCREMENTALLY from the day after the last bar
    h.fake.overrides["MSFT"] = generate_history("MSFT").loc[:DAY1]
    h.clock.set(DAY1_AFTER_CLOSE)
    day1 = md.fetch_price_history_yahoo("MSFT")
    h.fake.overrides.pop("MSFT")
    h.clock.set(AFTER_CLOSE)
    m = h.mark()
    day2 = md.fetch_price_history_yahoo("MSFT")
    incremental_calls = h.calls_since(m)
    assert day1.index.max() == pd.Timestamp(DAY1)
    assert [(c["start"], c["end"], c["period"]) for c in incremental_calls] == [
        ("2026-06-16", "<wall-clock today+1>", None)]
    assert day2.index.max() == AS_OF and day2.index.is_unique
    np.testing.assert_allclose(day2["Close"].to_numpy(), generate_history("MSFT")["Close"].to_numpy())
    assert h.cache_cls().get_cached_data("MSFT").index.max() == AS_OF

    # stale cache + Yahoo down -> stale data returned
    h.seed_disk("NVDA", end=DAY1)
    h.fake.fail.add("NVDA")
    m = h.mark()
    stale = md.fetch_price_history_yahoo("NVDA")
    stale_calls = h.calls_since(m)
    assert stale.index.max() == pd.Timestamp(DAY1)

    # no cache, no data -> ValueError
    h.fake.missing.add(NODATA)
    with pytest.raises(ValueError, match=re.escape(f"No data returned for ticker '{NODATA}'.")):
        md.fetch_price_history_yahoo(NODATA)
    with pytest.raises(ValueError, match=re.escape("Ticker is empty.")):
        md.fetch_price_history_yahoo(" ")

    period_1y = md.fetch_price_history_yahoo("AAPL", period="1y")

    assert_golden("chart_cascade", {
        "cold": frame_digest(cold),
        "calls": {"cold": cold_calls, "memory": memory_calls, "disk": disk_calls,
                  "incremental": incremental_calls, "stale_yahoo_down": stale_calls},
        "incremental_day1": frame_digest(day1),
        "incremental_day2": frame_digest(day2),
        "stale_yahoo_down": frame_digest(stale),
        "info_calls": h.info_calls(),
        "disk": h.disk_state(),
        # KNOWN-BUG:md-period-ignored
        "period_1y_rows": len(period_1y),
    }, area=AREA)


# ─────────────────────────────────────────────────────────────────────────────
# fetch_price_history_batch
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_price_history_batch_mixed(h):
    """Custom, memory-current, disk-current, disk-stale, cold, BTC, missing and unknown."""
    md = h.md
    h.seed_custom()
    md.fetch_price_history("MSFT", skip_live_bar=True)  # memory + disk current
    h.seed_disk("SPY")  # disk current
    h.seed_disk("QQQ", end=DAY1)  # disk stale
    h.fake.missing.add(NODATA)
    progress = []
    tickers = [f"[Custom] {CUSTOM_DAILY}", "aapl", " SPY ", "AAPL", "MSFT", "QQQ", "BTC-USD",
               f"[custom] {CUSTOM_MONTHLY.lower()}", "[Custom] _QT_TEST_unknown", NODATA]

    m = h.mark()
    out = md.fetch_price_history_batch(tickers, progress_callback=lambda *a: progress.append(list(a)))
    calls = h.calls_since(m)

    assert list(out) == [f"[Custom] {CUSTOM_DAILY}", f"[custom] {CUSTOM_MONTHLY.lower()}",
                         "SPY", "MSFT", "AAPL", "QQQ", "BTC-USD"]
    assert len(calls) == 1 and calls[0]["period"] == "max" and calls[0]["group_by"] == "ticker"
    assert calls[0]["tickers"] == ["AAPL", "QQQ", "BTC-USD", NODATA]
    assert progress[0] == [0, 6, "", "classifying"]  # 6 distinct standard tickers
    assert [p[3] for p in progress].count("cache") == 2
    assert [p[3] for p in progress].count("yahoo") == 4
    for t in ("SPY", "MSFT", "AAPL", "QQQ"):
        assert out[t].index.max() == AS_OF, t
        np.testing.assert_allclose(out[t]["Close"].to_numpy(), generate_history(t)["Close"].to_numpy())
    assert out["BTC-USD"].index.min() == BTC_CSV_FIRST
    monthly = out[f"[custom] {CUSTOM_MONTHLY.lower()}"]
    assert len(monthly) == 72 and monthly.index.max() == pd.Timestamp("2025-12-31")  # native monthly
    assert not (h.cache_dir / f"{NODATA}.parquet").exists()

    assert_golden("batch_mixed", {
        "keys": list(out),
        "results": {k: frame_digest(v) for k, v in out.items()},
        "calls": calls,
        "progress": progress,
        "info_calls": h.info_calls(),
        "disk": h.disk_state(),
    }, area=AREA)


def test_fetch_price_history_batch_edge_cases(h):
    md = h.md
    h.seed_custom()
    record = {}

    assert md.fetch_price_history_batch([]) == {}

    progress = []
    m = h.mark()
    only_custom = md.fetch_price_history_batch([f"[Custom] {CUSTOM_DAILY}"], lambda *a: progress.append(a))
    assert list(only_custom) == [f"[Custom] {CUSTOM_DAILY}"]
    assert h.calls_since(m) == [] and progress == []

    progress = []
    m = h.mark()
    single = md.fetch_price_history_batch(["aapl"], lambda *a: progress.append(list(a)))
    record["single_calls"] = h.calls_since(m)
    record["single_progress"] = progress
    record["single"] = frame_digest(single["AAPL"])
    assert record["single_calls"][0]["group_by"] == "column"
    assert progress == [[0, 1, "", "classifying"], [1, 1, "AAPL", "yahoo"]]
    pd.testing.assert_frame_equal(single["AAPL"], md.fetch_price_history("AAPL", skip_live_bar=True))

    # one failing ticker sinks the whole Yahoo download; cache-current tickers still load
    h.seed_disk("SPY")
    h.fake.fail.add(FAILING)
    progress = []
    m = h.mark()
    failed = md.fetch_price_history_batch(["SPY", "MSFT", FAILING], lambda *a: progress.append(list(a)))
    record["failure_calls"] = h.calls_since(m)
    record["failure_progress"] = progress
    assert list(failed) == ["SPY"]
    assert not (h.cache_dir / "MSFT.parquet").exists()
    record["disk"] = h.disk_state()

    assert_golden("batch_edge_cases", record, area=AREA)


def test_batch_full_history_chunks_large_requests(h, monkeypatch):
    """The batch path's Yahoo step splits more than 200 tickers into parallel chunks of
    at most 200 (a 1-ticker chunk uses group_by="column"), then fetches metadata once."""
    from app.services.ticker_metadata_service import TickerMetadataService

    metadata_requests = []
    monkeypatch.setattr(TickerMetadataService, "get_metadata_batch",
                        classmethod(lambda cls, tickers, *a, **k: metadata_requests.append(list(tickers)) or {}))
    base = generate_history("SPY").tail(10)
    names = [f"_QT_TEST_C{i:03d}" for i in range(201)]
    for i, name in enumerate(names):
        h.fake.overrides[name] = base * (1.0 + i / 1000.0)
    h.fake.missing.add(NODATA)
    progress = []
    out, failed = h.yahoo.fetch_batch_full_history(names + [NODATA], lambda *a: progress.append(a))

    assert sorted(out) == names and failed == [NODATA]
    chunks = sorted(h.fake.calls, key=lambda c: len(c["tickers"]))
    assert [(len(c["tickers"]), c["group_by"], c["period"]) for c in chunks] == [
        (2, "ticker", "max"), (200, "ticker", "max")]
    assert chunks[0]["tickers"] == [names[-1], NODATA]  # input order, 200 per chunk
    assert len(progress) == 2 and max(p[0] for p in progress) == 202 and {p[1] for p in progress} == {202}
    assert all(len(df) == 10 and list(df.columns) == OHLCV for df in out.values())
    np.testing.assert_allclose(out[names[7]]["Close"].to_numpy(), base["Close"].to_numpy() * 1.007)
    assert len(metadata_requests) == 1 and sorted(metadata_requests[0]) == names


# ─────────────────────────────────────────────────────────────────────────────
# Custom tickers
# ─────────────────────────────────────────────────────────────────────────────


def test_custom_tickers_bypass_yahoo_and_cache(h):
    md = h.md
    h.seed_custom()
    h.seed_disk("SPY")
    h.version_file.write_text("yahoo_v1")  # an outdated version must not be acted on for custom tickers
    daily = md.fetch_price_history(f"[Custom] {CUSTOM_DAILY}")
    same = md.fetch_price_history(f"  [custom]   {CUSTOM_DAILY.lower()} ")
    weekly = md.fetch_price_history(f"[Custom] {CUSTOM_DAILY}", interval="weekly")
    monthly = md.fetch_price_history_yahoo(f"[Custom] {CUSTOM_DAILY}", interval="monthly")
    monthly_fph = md.fetch_price_history(f"[Custom] {CUSTOM_DAILY}", interval="1mo")
    coarse_yearly = md.fetch_price_history(f"[Custom] {CUSTOM_MONTHLY}", interval="yearly")

    with pytest.raises(ValueError, match="cannot serve daily data"):
        md.fetch_price_history(f"[Custom] {CUSTOM_MONTHLY}")
    with pytest.raises(ValueError, match=re.escape("Unknown custom ticker: '[Custom] _QT_TEST_unknown'")):
        md.fetch_price_history("[Custom] _QT_TEST_unknown")
    with pytest.raises(ValueError, match=re.escape("Unknown custom ticker: '[Custom] _QT_TEST_unknown'")):
        md.fetch_price_history_yahoo("[Custom] _QT_TEST_unknown")

    pd.testing.assert_frame_equal(same, daily)
    pd.testing.assert_frame_equal(monthly_fph, monthly)
    assert list(daily.columns) == OHLCV
    assert (daily["Open"] == daily["Close"]).all() and (daily["High"] == daily["Low"]).all()
    assert (daily["Volume"] == 0).all()
    from app.services.custom_data_service import get_custom_returns
    returns = get_custom_returns(CUSTOM_DAILY)
    np.testing.assert_allclose(daily["Close"].to_numpy(), 100.0 * (1.0 + returns).cumprod().to_numpy())
    # compounding resample: the last weekly close equals the last daily close
    assert weekly["Close"].iloc[-1] == pytest.approx(daily["Close"].iloc[-1])
    assert h.fake.calls == []
    # the intercept runs before the version check: nothing wiped, nothing written
    assert [p.name for p in h.cache_dir.glob("*.parquet")] == ["SPY.parquet"]
    assert h.version_file.read_text() == "yahoo_v1"
    assert set(h.spy.reads) == {f"custom_data/series/{CUSTOM_DAILY}.parquet",
                                f"custom_data/series/{CUSTOM_MONTHLY}.parquet"}

    assert_golden("custom_tickers", {
        "daily": frame_digest(daily),
        "weekly": frame_digest(weekly),
        "monthly": frame_digest(monthly),
        "monthly_import_yearly": frame_digest(coarse_yearly),
    }, area=AREA)


# ─────────────────────────────────────────────────────────────────────────────
# MarketDataCache staleness rule (NYSE calendar / crypto)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ticker, last_bar, now_et, expected", [
    ("AAPL", "2026-06-30", "2026-06-30 15:59", True),   # before the close: yesterday is enough
    ("AAPL", "2026-06-29", "2026-06-30 15:59", True),
    ("AAPL", "2026-06-29", "2026-06-30 16:00", False),  # after the close today's bar is expected
    ("AAPL", "2026-06-30", "2026-06-30 16:00", True),
    ("AAPL", "2026-06-26", "2026-06-29 09:00", True),   # Monday pre-open: Friday is the last session
    ("AAPL", "2026-06-25", "2026-06-29 09:00", False),
    ("AAPL", "2026-07-02", "2026-07-04 12:00", True),   # Fri 07-03 is the observed July 4th holiday
    ("AAPL", "2026-07-01", "2026-07-04 12:00", False),
    ("AAPL", "2026-06-18", "2026-06-19 18:00", True),   # Juneteenth
    ("AAPL", "2026-04-02", "2026-04-03 18:00", True),   # Good Friday
    ("^GSPC", "2026-06-29", "2026-06-30 18:00", False),
    ("BTC-USD", "2026-06-30", "2026-06-30 00:05", True),  # crypto: needs today's bar, any hour
    ("BTC-USD", "2026-06-29", "2026-06-30 00:05", False),
    ("BTC-USD", "2026-07-03", "2026-07-04 12:00", False),  # no weekend/holiday grace for crypto
    ("eth-usdt", "2026-06-30", "2026-06-30 23:59", True),
    ("ETH-USDT", "2026-06-29", "2026-06-30 23:59", False),
])
def test_is_cache_current_calendar(h, ticker, last_bar, now_et, expected):
    cache = h.cache_cls()
    df = pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.to_datetime(["2026-01-02", last_bar]))
    h.clock.set(now_et)
    assert cache.is_cache_current(ticker, df=df) is expected
    assert h.spy.reads == []  # df given: no parquet read
    cache.save_to_cache(ticker, df)
    assert cache.is_cache_current(ticker) is expected  # df omitted: reads the parquet
    assert len(h.spy.reads) == 1


def test_is_cache_current_without_data(h):
    cache = h.cache_cls()
    assert cache.is_cache_current("AAPL") is False  # no file
    assert cache.is_cache_current("AAPL", df=pd.DataFrame()) is False
    assert h.spy.reads == []


# ─────────────────────────────────────────────────────────────────────────────
# Parquet read counts (P2 B-cache perf fix)
# ─────────────────────────────────────────────────────────────────────────────


def _scenario_reads(h, scenario: str) -> tuple:
    """Run ``scenario``'s setup, then return (reads during the measured call, files expected)."""
    md = h.md
    trio = ["AAPL", "MSFT", "SPY"]
    if scenario == "fph_memory_hit":
        md.fetch_price_history("AAPL", skip_live_bar=True)
        m = h.mark()
        md.fetch_price_history("AAPL", skip_live_bar=True)
        return h.reads_since(m), {"cache/AAPL.parquet"}
    if scenario == "fph_disk_hit":
        h.seed_disk("AAPL")
        m = h.mark()
        md.fetch_price_history("AAPL", skip_live_bar=True)
        return h.reads_since(m), {"cache/AAPL.parquet"}
    if scenario == "fph_stale_yahoo_down":
        h.seed_disk("AAPL", end=DAY1)
        h.fake.fail.add("AAPL")
        m = h.mark()
        md.fetch_price_history("AAPL", skip_live_bar=True)
        return h.reads_since(m), {"cache/AAPL.parquet"}
    if scenario == "chart_memory_hit":
        md.fetch_price_history_yahoo("AAPL")
        m = h.mark()
        md.fetch_price_history_yahoo("AAPL")
        return h.reads_since(m), {"cache/AAPL.parquet"}
    if scenario == "chart_disk_hit":
        h.seed_disk("AAPL")
        m = h.mark()
        md.fetch_price_history_yahoo("AAPL")
        return h.reads_since(m), {"cache/AAPL.parquet"}
    if scenario == "batch_memory_hit":
        md.fetch_price_history_batch(trio)
        m = h.mark()
        md.fetch_price_history_batch(trio)
        return h.reads_since(m), {f"cache/{t}.parquet" for t in trio}
    if scenario == "batch_disk_hit":
        for t in trio:
            h.seed_disk(t)
        m = h.mark()
        md.fetch_price_history_batch(trio)
        return h.reads_since(m), {f"cache/{t}.parquet" for t in trio}
    if scenario == "custom":
        h.seed_custom()
        m = h.mark()
        md.fetch_price_history(f"[Custom] {CUSTOM_DAILY}")
        return h.reads_since(m), {f"custom_data/series/{CUSTOM_DAILY}.parquet"}
    raise AssertionError(scenario)


# Reads per measured call at BASE (budget = today's count; fewer is fine).
READ_BUDGET = {
    "fph_memory_hit": 1,        # is_cache_current() re-reads the parquet despite the memory hit
    "fph_disk_hit": 2,          # get_cached_data + is_cache_current
    "fph_stale_yahoo_down": 3,  # get_cached_data + is_cache_current + stale fallback read
    "chart_memory_hit": 1,
    "chart_disk_hit": 2,
    "batch_memory_hit": 3,      # 1 per ticker
    "batch_disk_hit": 6,        # 2 per ticker
    "custom": 1,
}

# Reads per measured call once is_cache_current() is given the frame already loaded.
READ_TARGET = {
    "fph_memory_hit": 0,
    "fph_disk_hit": 1,
    "chart_memory_hit": 0,
    "chart_disk_hit": 1,
    "batch_memory_hit": 0,
    "batch_disk_hit": 3,
}


@pytest.mark.parametrize("scenario", sorted(READ_BUDGET))
def test_parquet_read_budget(h, scenario):
    reads, expected_files = _scenario_reads(h, scenario)
    assert set(reads) <= expected_files, reads
    assert len(reads) <= READ_BUDGET[scenario], reads
    if scenario in ("fph_stale_yahoo_down", "custom"):
        assert len(reads) >= 1  # these paths really must read the file


_REREAD_BUG = pytest.mark.xfail(strict=True, reason=(
    "KNOWN-BUG:md-parquet-reread - market_data calls MarketDataCache.is_cache_current(ticker) without "
    "df= at all 6 call sites, so memory hits read the parquet once and disk hits twice; fixed in P2 B-cache"))


@_REREAD_BUG
@pytest.mark.parametrize("scenario", sorted(READ_TARGET))
def test_parquet_read_target(h, scenario):
    reads, _ = _scenario_reads(h, scenario)
    assert len(reads) == READ_TARGET[scenario], reads


@_REREAD_BUG
@pytest.mark.parametrize("entry", ["fetch_price_history", "fetch_price_history_yahoo"])
def test_memory_frame_freshness_is_judged_on_itself(h, entry):
    """Today a stale in-memory frame is served whenever the parquet on disk is current."""
    md = h.md
    fn = getattr(md, entry)
    kwargs = {"skip_live_bar": True} if entry == "fetch_price_history" else {}
    h.seed_disk("AAPL", end=DAY1)
    h.clock.set(DAY1_AFTER_CLOSE)
    assert fn("AAPL", **kwargs).index.max() == pd.Timestamp(DAY1)  # memory now holds DAY1 data
    h.seed_disk("AAPL")  # another process refreshed the parquet through AS_OF
    h.clock.set(AFTER_CLOSE)
    assert fn("AAPL", **kwargs).index.max() == AS_OF


# ─────────────────────────────────────────────────────────────────────────────
# Other known bugs (P7)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN-BUG:md-btc-chart-no-prepend - fetch_price_history_yahoo never prepends "
    "bitcoin_historical_prices.csv, and the other paths then serve the chart's cache as-is"))
def test_btc_prepend_on_chart_path(h):
    md = h.md
    chart = md.fetch_price_history_yahoo("BTC-USD")
    h.drop_memory()
    after = md.fetch_price_history("BTC-USD", skip_live_bar=True)
    assert chart.index.min() == BTC_CSV_FIRST
    assert after.index.min() == BTC_CSV_FIRST


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN-BUG:md-period-ignored - the single-ticker fetch functions accept period= but "
    "always return the full history"))
@pytest.mark.parametrize("entry", ["fetch_price_history", "fetch_price_history_yahoo"])
def test_period_argument_limits_history(h, entry):
    md = h.md
    kwargs = {"skip_live_bar": True} if entry == "fetch_price_history" else {}
    out = getattr(md, entry)("AAPL", period="1y", **kwargs)
    assert out.index.min() >= AS_OF - pd.DateOffset(years=1)
    assert out.index.max() == AS_OF


# ─────────────────────────────────────────────────────────────────────────────
# YahooFinanceService (the yfinance gateway)
# ─────────────────────────────────────────────────────────────────────────────


def test_yahoo_finance_service_methods(h):
    ys = h.yahoo
    fake = h.fake
    fake.missing.add(NODATA)
    fake.fail.add(FAILING)
    rec = {}

    def run(label, fn):
        m = h.mark()
        value = fn()
        rec[label] = {"calls": h.calls_since(m), "value": value}
        return value

    hist = run("fetch_historical", lambda: frame_digest(ys.fetch_historical("aapl", "2026-06-01", "2026-06-30")))
    assert hist["index"]["end"] == "2026-06-29"  # end is exclusive
    run("fetch_historical_missing", lambda: frame_digest(ys.fetch_historical(NODATA, "2026-06-01", "2026-06-30")))
    run("fetch_historical_failure", lambda: frame_digest(ys.fetch_historical(FAILING, "2026-06-01", "2026-06-30")))
    today = run("fetch_today_ohlcv", lambda: frame_digest(ys.fetch_today_ohlcv("btc-usd")))
    assert today["shape"] == [1, 5] and today["index"]["start"] == "2026-06-30"
    assert run("fetch_today_ohlcv_missing", lambda: ys.fetch_today_ohlcv(NODATA)) is None
    vix = run("fetch_full_history_index", lambda: frame_digest(ys.fetch_full_history("^VIX")))
    assert vix["columns"] == OHLCV
    safe_missing = run("fetch_full_history_safe_missing",
                       lambda: [frame_digest(x) if isinstance(x, pd.DataFrame) else x
                                for x in ys.fetch_full_history_safe(NODATA)])
    assert safe_missing[1] is True and safe_missing[0]["shape"] == [0, 0]
    run("fetch_full_history_safe_ok", lambda: ys.fetch_full_history_safe("SPY")[1])

    def batch_full():
        res, failed = ys.fetch_batch_full_history(["aapl", "BTC-USD", NODATA, "AAPL"])
        return {"results": {k: frame_digest(v) for k, v in res.items()}, "failed": failed}

    bf = run("fetch_batch_full_history", batch_full)
    assert sorted(bf["results"]) == ["AAPL", "BTC-USD"] and bf["failed"] == [NODATA]

    def date_range():
        res = ys.fetch_batch_date_range(
            ["AAPL", "SPY", "BTC-USD", "QQQ"],
            {"AAPL": ("2026-06-01", "2026-06-15"), "SPY": ("2026-06-01", "2026-06-15"),
             "BTC-USD": ("2026-06-10", "2026-06-20")})
        return {k: frame_digest(v) for k, v in res.items()}

    dr = run("fetch_batch_date_range", date_range)
    assert sorted(dr) == ["AAPL", "BTC-USD", "SPY"]  # QQQ has no range -> skipped
    assert len(rec["fetch_batch_date_range"]["calls"]) == 2

    multi = run("fetch_batch_current_prices", lambda: ys.fetch_batch_current_prices(["aapl", "spy"]))
    assert multi["AAPL"] == pytest.approx(float(generate_history("AAPL")["Close"].iloc[-1]))  # raw close
    run("fetch_batch_current_prices_single", lambda: ys.fetch_batch_current_prices(["BTC-USD"]))
    assert run("fetch_batch_current_prices_missing", lambda: ys.fetch_batch_current_prices([NODATA])) == {}
    run("fetch_batch_short_history", lambda: frame_digest(ys.fetch_batch_short_history(["AAPL", "SPY"], "5d")))
    run("fetch_batch_short_history_single", lambda: frame_digest(ys.fetch_batch_short_history(["^VIX"], "1mo")))
    assert run("is_valid_ticker", lambda: ys.is_valid_ticker("aapl")) is True
    assert run("is_valid_ticker_missing", lambda: ys.is_valid_ticker(NODATA)) is False
    assert run("is_valid_ticker_failure", lambda: ys.is_valid_ticker(FAILING)) is False

    rec["info_calls"] = h.info_calls()
    assert_golden("yahoo_service_methods", rec, area=AREA)
