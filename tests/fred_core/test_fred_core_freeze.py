"""KNOWN-BUG:fred-freeze - a lagging lower-frequency series in a mixed group freezes.

``_fetch_incremental`` asks EVERY series of a group only for observations
dated on/after the group's newest row (``cached.index.max()``) and then
forward-fills.  A monthly/quarterly observation is dated at the start of its
period but published weeks later, when the daily/weekly members have already
pushed the group's newest row past that date - so it is never fetched, and
the forward-fill keeps showing the old value on every new row, looking current.

Each scenario replays three fetch "rounds" whose FakeFred release cut-offs
mimic real publication lags::

    round  daily/weekly  monthly     quarterly
    R0     2026-05-15    2026-04-01  2026-01-01   (full fetch, no cache)
    R1     2026-06-10    2026-05-01  2026-01-01   (incremental)
    R2     2026-06-30    2026-06-01  2026-04-01   (incremental)

The plain tests pin TODAY's (frozen) output so a refactor is visible; the
``xfail(strict=True)`` tests assert the correct behaviour and must be flipped
by the fix (P4).  Between rounds :func:`_let_time_pass` clears the cooldown
timestamps (P4: also expire fetch-time TTLs there).  Caches are stale because
FakeFred data ends 2026-06-30 and freshness is judged by the real clock.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from fixtures.fake_fred import END_DATE
from fred_core.fred_core_support import reset_fetch_cooldowns

ROUNDS = {
    0: {"D": "2026-05-15", "W": "2026-05-15", "M": "2026-04-01", "Q": "2026-01-01"},
    1: {"D": "2026-06-10", "W": "2026-06-10", "M": "2026-05-01", "Q": "2026-01-01"},
    2: {"D": "2026-06-30", "W": "2026-06-30", "M": "2026-06-01", "Q": "2026-04-01"},
}
MIXED = {"10Y": "DGS10", "U-3": "UNRATE", "Real GDP": "GDPC1"}  # D + M + Q
FREEZE_REASON = ("KNOWN-BUG:fred-freeze incremental FRED fetch starts at the group's newest row, "
                 "so a lagging lower-frequency series in a mixed group never receives new "
                 "observations and is forward-filled forever")


def _assume_fake_data_is_stale():
    # FakeFred ends 2026-06-30; the longest max_age used here is 45 days.
    assert date.today() > date(2026, 8, 15), "these scenarios need the real clock past 2026-08-15"


def _release(ctl, series_ids, rnd):
    """Make FakeFred publish only what was out at round ``rnd``."""
    cut = ROUNDS[rnd]
    ctl.end_dates.clear()
    for sid in series_ids:
        ctl.end_dates[sid] = cut[ctl.frequencies[sid]]
    ctl.reset_calls()


def _let_time_pass(monkeypatch, cls):
    reset_fetch_cooldowns(monkeypatch, cls)


def _starts(ctl):
    return {start for _, start, _ in ctl.calls}


def _assert_distinct(values):
    assert len(set(values)) == len(values), f"fixture precondition: values must differ {values}"


# ── Synthetic mixed group through BaseFredService._get_group ─────────────────


def _run_probe_rounds(env, probe_service, monkeypatch):
    _assume_fake_data_is_stale()
    cls = probe_service()
    cache_file = env.cache_file("_qt_test_freeze_mixed.parquet")
    starts = []
    out = None
    for rnd in (0, 1, 2):
        _release(env.ctl, MIXED.values(), rnd)
        _let_time_pass(monkeypatch, cls)
        out = cls._get_group(MIXED, cache_file, "_last_probe_fetch", 45)
        starts.append(_starts(env.ctl))
    env.ctl.end_dates.clear()
    return out, starts


def test_mixed_group_lagging_series_current_frozen_behaviour(fred_env, probe_service, monkeypatch):
    out, starts = _run_probe_rounds(fred_env, probe_service, monkeypatch)
    ctl = fred_env.ctl
    unrate, gdp, dgs10 = ctl.series("UNRATE"), ctl.series("GDPC1"), ctl.series("DGS10")
    _assert_distinct([unrate.loc[d] for d in ("2026-04-01", "2026-05-01", "2026-06-01")])
    _assert_distinct([gdp.loc[d] for d in ("2026-01-01", "2026-04-01")])

    # every series is asked only for data on/after the group's newest row
    assert starts == [{None}, {"2026-05-15"}, {"2026-06-10"}]
    # the daily member is complete and current
    assert out.index.max() == END_DATE
    assert out.loc["2026-06-30", "10Y"] == dgs10.loc["2026-06-30"]
    # ... but the monthly member is stuck at April and the quarterly one at Q1,
    # forward-filled onto every new row so they look current
    assert out.loc["2026-04-01":, "U-3"].unique().tolist() == [unrate.loc["2026-04-01"]]
    assert out.loc["2026-01-01":, "Real GDP"].unique().tolist() == [gdp.loc["2026-01-01"]]
    assert out["U-3"].last_valid_index() == END_DATE
    assert "2026-05-01" in out.index.strftime("%Y-%m-%d")  # the row exists, value is stale
    # the frozen frame is what sits in the cache for the next session
    cached = pd.read_parquet(fred_env.cache_file("_qt_test_freeze_mixed.parquet"))
    assert cached.loc["2026-06-30", "U-3"] == unrate.loc["2026-04-01"]


@pytest.mark.xfail(strict=True, reason=FREEZE_REASON)
def test_mixed_group_lagging_series_receives_new_observations(fred_env, probe_service, monkeypatch):
    out, _ = _run_probe_rounds(fred_env, probe_service, monkeypatch)
    ctl = fred_env.ctl
    unrate, gdp = ctl.series("UNRATE"), ctl.series("GDPC1")

    for d in ("2026-04-01", "2026-05-01", "2026-06-01"):
        assert out["U-3"].dropna().asof(pd.Timestamp(d)) == unrate.loc[d], d
    assert out["Real GDP"].dropna().asof(pd.Timestamp("2026-04-01")) == gdp.loc["2026-04-01"]
    assert out["U-3"].dropna().iloc[-1] == unrate.iloc[-1]
    assert out["Real GDP"].dropna().iloc[-1] == gdp.iloc[-1]


# ── Real service: GdpFredService (quarterly GDP shares a group with monthly USREC) ─


def _run_gdp_rounds(env, monkeypatch):
    from app.ui.modules.gdp.services.gdp_fred_service import (
        PRODUCTION_SERIES,
        QUARTERLY_SERIES,
        GdpFredService,
    )

    _assume_fake_data_is_stale()
    ids = list(QUARTERLY_SERIES.values()) + list(PRODUCTION_SERIES.values())
    starts, result = [], None
    for rnd in (0, 1, 2):
        _release(env.ctl, ids, rnd)
        _let_time_pass(monkeypatch, GdpFredService)
        result = GdpFredService.fetch_all_data()
        starts.append({(sid, start) for sid, start, _ in env.ctl.calls if sid == "GDPC1"})
    env.ctl.end_dates.clear()
    return result, starts


def test_gdp_quarterly_group_current_frozen_behaviour(fred_env, monkeypatch):
    result, starts = _run_gdp_rounds(fred_env, monkeypatch)
    gdp = fred_env.ctl.series("GDPC1")
    usrec = fred_env.ctl.series("USREC")
    _assert_distinct([gdp.loc["2026-01-01"], gdp.loc["2026-04-01"]])

    # the group's newest row is the monthly USREC date, so GDPC1 is asked from there
    assert starts == [{("GDPC1", None)}, {("GDPC1", "2026-04-01")}, {("GDPC1", "2026-05-01")}]
    real = result["gdp"]["Real GDP"]
    assert real.index.max() == pd.Timestamp("2026-06-01")
    assert real.loc["2026-01-01":].unique().tolist() == [pytest.approx(gdp.loc["2026-01-01"] / 1000)]
    assert result["usrec"]["USREC"].iloc[-1] == usrec.loc["2026-06-01"]


@pytest.mark.xfail(strict=True, reason=FREEZE_REASON)
def test_gdp_quarterly_group_receives_the_new_quarter(fred_env, monkeypatch):
    result, _ = _run_gdp_rounds(fred_env, monkeypatch)
    gdp = fred_env.ctl.series("GDPC1")

    real = result["gdp"]["Real GDP"].dropna()
    assert real.asof(pd.Timestamp("2026-04-01")) == pytest.approx(gdp.loc["2026-04-01"] / 1000)
    assert real.iloc[-1] == pytest.approx(gdp.iloc[-1] / 1000)


# ── Real service: TreasuryFredService (monthly Fed Funds in the daily yield group) ─


def _run_treasury_rounds(env, monkeypatch):
    from app.ui.modules.treasury.services.treasury_fred_service import ALL_SERIES, TreasuryFredService

    _assume_fake_data_is_stale()
    monkeypatch.setattr(TreasuryFredService, "_last_fetch_time", None)
    starts, df = [], None
    for rnd in (0, 1, 2):
        _release(env.ctl, ALL_SERIES.values(), rnd)
        df = TreasuryFredService.fetch_all_treasury_data()
        starts.append(_starts(env.ctl))
        # new rows arrived -> the service cleared its own cooldown (no manual reset)
        assert TreasuryFredService._last_fetch_time is None
    env.ctl.end_dates.clear()
    return df, starts


def test_treasury_fed_funds_current_frozen_behaviour(fred_env, monkeypatch):
    df, starts = _run_treasury_rounds(fred_env, monkeypatch)
    fedfunds = fred_env.ctl.series("FEDFUNDS")
    _assert_distinct([fedfunds.loc[d] for d in ("2026-04-01", "2026-05-01", "2026-06-01")])

    assert starts == [{None}, {"2026-05-15"}, {"2026-06-10"}]
    assert df.index.max() == END_DATE
    assert df.loc["2026-06-30", "10Y"] == fred_env.ctl.series("DGS10").loc["2026-06-30"]
    assert df.loc["2026-04-01":, "Fed Funds"].unique().tolist() == [fedfunds.loc["2026-04-01"]]


@pytest.mark.xfail(strict=True, reason=FREEZE_REASON)
def test_treasury_fed_funds_receives_new_observations(fred_env, monkeypatch):
    df, _ = _run_treasury_rounds(fred_env, monkeypatch)
    fedfunds = fred_env.ctl.series("FEDFUNDS")

    for d in ("2026-05-01", "2026-06-01"):
        assert df["Fed Funds"].dropna().asof(pd.Timestamp(d)) == fedfunds.loc[d], d
