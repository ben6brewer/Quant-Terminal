"""Characterization of ``BaseFredService._get_group`` and its helpers (P0.T1).

Paths covered: no cache -> full fetch; fresh cache -> served as is; stale
cache -> incremental fetch from the last cached date; the 1-hour cooldown;
failure / no-key / corrupt-cache fallbacks; the declarative ``GROUPS`` ->
``fetch_all_data`` mechanics; ``_latest_value`` / ``_compute_yoy``.

Freshness is judged by ``date.today()``: FakeFred data ends 2026-06-30, so a
cache built from it is always stale; "fresh" caches are synthetic frames
dated relative to the real clock.  Each test uses its own probe subclass
(``probe_service``), so class-level cooldown timestamps never leak.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.base_fred_service import BaseFredService
from app.services.fred_group import FredGroup, FredOutput

MIXED = {"10Y": "DGS10", "U-3": "UNRATE"}  # daily + monthly
MONTHLY = {"U-3": "UNRATE", "Payrolls": "PAYEMS"}
ATTR = "_last_probe_fetch"
CACHE_NAME = "_qt_test_probe_group.parquet"


def _truth_frame(ctl, series_map, **slice_kw):
    """What ``_fetch_full`` builds from ``series_map``: ffilled union, all-NaN rows dropped."""
    df = pd.DataFrame({label: ctl.series(sid, **slice_kw) for label, sid in series_map.items()})
    df.index.name = "Date"
    return df.ffill().dropna(how="all")


def _assert_frame(actual, expected):
    pd.testing.assert_frame_equal(
        actual[sorted(actual.columns)], expected[sorted(expected.columns)],
        check_freq=False, check_index_type=True,
    )


def _synthetic_cache(env, path, last_day: date, columns, periods=5):
    """Seed a cache parquet (and a current version file, so the one-time version
    check does not wipe it) whose newest row is ``last_day``."""
    env.write_current_version()
    idx = pd.date_range(end=pd.Timestamp(last_day), periods=periods, freq="D", name="Date")
    df = pd.DataFrame({c: np.arange(periods, dtype="float64") + i for i, c in enumerate(columns)},
                      index=idx)
    df.to_parquet(path)
    return pd.read_parquet(path)  # exactly what is on disk (parquet may change the time unit)


def _build_stale_cache(cls, env, series_map, cutoffs):
    """Full fetch while FakeFred only has data up to ``cutoffs`` ({id: date}), then
    'release' everything.  Returns the cached frame (stale vs. the real clock)."""
    env.ctl.end_dates.update(cutoffs)
    cached = cls._get_group(series_map, env.cache_file(CACHE_NAME), ATTR, 45)
    env.ctl.end_dates.clear()
    env.ctl.reset_calls()
    assert getattr(cls, ATTR, None) is None  # the full-fetch path never arms the cooldown
    return cached


# ── No cache -> full fetch ──────────────────────────────────────────────────


def test_no_cache_full_fetch_returns_ffilled_union_and_saves_parquet(fred_env, probe_service):
    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)

    out = cls._get_group(MIXED, cache_file, ATTR, 45)

    assert sorted(fred_env.ctl.calls) == [("DGS10", None, None), ("UNRATE", None, None)]
    expected = _truth_frame(fred_env.ctl, MIXED)
    _assert_frame(out, expected)
    assert out.index.name == "Date" and out.index.max() == pd.Timestamp("2026-06-30")
    # ffill: the daily holiday NaN takes the previous close, the monthly value
    # is carried onto every business day of its month.
    dgs10 = fred_env.ctl.series("DGS10")
    assert np.isnan(dgs10.loc["2026-01-01"])
    assert out.loc["2026-01-01", "10Y"] == dgs10.loc["2025-12-31"]
    assert out.loc["2026-01-15", "U-3"] == fred_env.ctl.series("UNRATE").loc["2026-01-01"]
    # parquet cache == returned frame; the cooldown is not armed on this path
    _assert_frame(pd.read_parquet(cache_file), out)
    assert getattr(cls, ATTR, None) is None


def test_full_fetch_partial_failure_drops_the_failed_series(fred_env, probe_service, caplog):
    cls = probe_service()
    fred_env.ctl.fail.add("UNRATE")

    with caplog.at_level(logging.ERROR):
        out = cls._get_group(MIXED, fred_env.cache_file(CACHE_NAME), ATTR, 45)

    assert list(out.columns) == ["10Y"]
    assert "FRED fetch failed for series U-3" in caplog.text
    assert list(pd.read_parquet(fred_env.cache_file(CACHE_NAME)).columns) == ["10Y"]


def test_full_fetch_total_failure_returns_none_without_cache(fred_env, probe_service):
    cls = probe_service()
    fred_env.ctl.fail.update(MIXED.values())

    assert cls._get_group(MIXED, fred_env.cache_file(CACHE_NAME), ATTR, 45) is None
    assert not fred_env.cache_file(CACHE_NAME).exists()


def test_no_api_key_and_no_cache_returns_none_without_fetching(fred_env, probe_service, monkeypatch):
    from app.services.fred_api_key_service import FredApiKeyService

    monkeypatch.setattr(FredApiKeyService, "_api_key", None)
    cls = probe_service()

    assert cls._get_group(MIXED, fred_env.cache_file(CACHE_NAME), ATTR, 45) is None
    assert fred_env.ctl.calls == [] and fred_env.ctl.instances == 0


# ── Fresh cache ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("age_days", [0, 45])
def test_fresh_cache_is_served_without_fetching(fred_env, probe_service, age_days):
    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)
    written = _synthetic_cache(fred_env, cache_file, date.today() - timedelta(days=age_days),
                               ["10Y", "U-3", "_QT_TEST_unknown"])

    out = cls._get_group(MIXED, cache_file, ATTR, 45)

    # only the columns of the series map survive; nothing is fetched
    pd.testing.assert_frame_equal(out, written[["10Y", "U-3"]], check_freq=False)
    assert fred_env.ctl.calls == [] and fred_env.ctl.instances == 0
    assert getattr(cls, ATTR, None) is None


def test_fresh_cache_is_served_even_without_api_key(fred_env, probe_service, monkeypatch):
    from app.services.fred_api_key_service import FredApiKeyService

    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)
    written = _synthetic_cache(fred_env, cache_file, date.today(), ["10Y", "U-3"])
    monkeypatch.setattr(FredApiKeyService, "_api_key", None)

    out = cls._get_group(MIXED, cache_file, ATTR, 45)

    pd.testing.assert_frame_equal(out, written, check_freq=False)


def test_is_cache_fresh_boundary():
    today = date.today()
    assert BaseFredService._is_cache_fresh(today, 45) is True
    assert BaseFredService._is_cache_fresh(today - timedelta(days=45), 45) is True
    assert BaseFredService._is_cache_fresh(today - timedelta(days=46), 45) is False
    assert BaseFredService._is_cache_fresh(today - timedelta(days=1), 0) is False


def test_cache_one_day_past_max_age_goes_incremental(fred_env, probe_service):
    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)
    last = date.today() - timedelta(days=46)
    written = _synthetic_cache(fred_env, cache_file, last, ["10Y", "U-3"])

    out = cls._get_group(MIXED, cache_file, ATTR, 45)

    # incremental request from the last cached day; FakeFred has nothing that
    # new (it ends 2026-06-30), so the cached frame comes back untouched
    assert sorted(fred_env.ctl.calls) == [("DGS10", last.isoformat(), None),
                                          ("UNRATE", last.isoformat(), None)]
    pd.testing.assert_frame_equal(out, written, check_freq=False)
    assert isinstance(getattr(cls, ATTR), float)


# ── Stale cache -> incremental ───────────────────────────────────────────────


def test_stale_cache_fetches_incrementally_from_last_cached_date(fred_env, probe_service):
    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)
    cached = _build_stale_cache(cls, fred_env, MIXED, {"DGS10": "2026-03-31", "UNRATE": "2026-03-01"})
    assert cached.index.max() == pd.Timestamp("2026-03-31")
    before = time.monotonic()

    out = cls._get_group(MIXED, cache_file, ATTR, 45)

    assert sorted(fred_env.ctl.calls) == [("DGS10", "2026-03-31", None), ("UNRATE", "2026-03-31", None)]
    # history up to the old last date is kept as cached; new rows are appended
    _assert_frame(out.loc[: "2026-03-31"], cached)
    assert out.index.max() == pd.Timestamp("2026-06-30")
    assert out.index.is_monotonic_increasing and out.index.is_unique
    unrate = fred_env.ctl.series("UNRATE")
    for month in ("2026-04-01", "2026-05-01", "2026-06-01"):
        assert out.loc[month, "U-3"] == unrate.loc[month]
    dgs10 = fred_env.ctl.series("DGS10").loc["2026-04-01":].ffill()
    pd.testing.assert_series_equal(out.loc["2026-04-01":, "10Y"], dgs10, check_names=False,
                                   check_freq=False)
    # merged frame is written back and the cooldown is armed (even on success)
    _assert_frame(pd.read_parquet(cache_file), out)
    assert before <= getattr(cls, ATTR) <= time.monotonic()


def test_incremental_overlap_row_takes_the_newly_fetched_value(fred_env, probe_service):
    cls = probe_service()
    base = fred_env.ctl.series("UNRATE")
    fred_env.ctl.overrides["UNRATE"] = base
    _build_stale_cache(cls, fred_env, {"U-3": "UNRATE"}, {"UNRATE": "2026-05-01"})
    revised = base.copy()
    revised.loc["2026-05-01"] = 42.0
    fred_env.ctl.overrides["UNRATE"] = revised

    out = cls._get_group({"U-3": "UNRATE"}, fred_env.cache_file(CACHE_NAME), ATTR, 45)

    assert out.loc["2026-05-01", "U-3"] == 42.0
    assert out.loc["2026-06-01", "U-3"] == base.loc["2026-06-01"]


def test_revisions_before_the_last_cached_date_are_ignored(fred_env, probe_service):
    """CURRENT behaviour: only observations dated >= the cache's last row are re-read."""
    cls = probe_service()
    base = fred_env.ctl.series("PAYEMS")
    fred_env.ctl.overrides["PAYEMS"] = base
    _build_stale_cache(cls, fred_env, MONTHLY, {"UNRATE": "2026-05-01", "PAYEMS": "2026-05-01"})
    revised = base.copy()
    revised.loc["2026-04-01"] = base.loc["2026-04-01"] + 250.0
    fred_env.ctl.overrides["PAYEMS"] = revised

    out = cls._get_group(MONTHLY, fred_env.cache_file(CACHE_NAME), ATTR, 45)

    assert {c[1] for c in fred_env.ctl.calls} == {"2026-05-01"}
    assert out.loc["2026-04-01", "Payrolls"] == base.loc["2026-04-01"]  # revision missed
    assert out.loc["2026-06-01", "Payrolls"] == base.loc["2026-06-01"]


@pytest.mark.xfail(strict=True, reason="KNOWN-BUG:fred-revisions incremental fetch starts at the "
                                       "last cached row, so FRED revisions to earlier observations "
                                       "are never picked up (P4: revision window)")
def test_revisions_within_the_revision_window_are_picked_up(fred_env, probe_service):
    cls = probe_service()
    base = fred_env.ctl.series("PAYEMS")
    fred_env.ctl.overrides["PAYEMS"] = base
    _build_stale_cache(cls, fred_env, MONTHLY, {"UNRATE": "2026-05-01", "PAYEMS": "2026-05-01"})
    revised = base.copy()
    revised.loc["2026-04-01"] = base.loc["2026-04-01"] + 250.0
    fred_env.ctl.overrides["PAYEMS"] = revised

    out = cls._get_group(MONTHLY, fred_env.cache_file(CACHE_NAME), ATTR, 45)

    assert out["Payrolls"].dropna().asof(pd.Timestamp("2026-04-01")) == revised.loc["2026-04-01"]


def test_series_added_to_an_existing_group_only_gets_data_after_the_cache_end(
        fred_env, probe_service):
    """CURRENT behaviour: a label missing from the cache is fetched incrementally too."""
    cls = probe_service()
    _build_stale_cache(cls, fred_env, {"10Y": "DGS10"}, {"DGS10": "2026-03-31"})

    out = cls._get_group(MIXED, fred_env.cache_file(CACHE_NAME), ATTR, 45)

    assert ("UNRATE", "2026-03-31", None) in fred_env.ctl.calls
    assert out["U-3"].first_valid_index() == pd.Timestamp("2026-04-01")
    assert out.loc[: "2026-03-31", "U-3"].isna().all()


@pytest.mark.xfail(strict=True, reason="KNOWN-BUG:fred-new-series-history a series added to an "
                                       "existing cached group is only fetched from the cache's last "
                                       "date, so it never gets its history (P4: per-series store)")
def test_series_added_to_an_existing_group_gets_full_history(fred_env, probe_service):
    cls = probe_service()
    _build_stale_cache(cls, fred_env, {"10Y": "DGS10"}, {"DGS10": "2026-03-31"})

    out = cls._get_group(MIXED, fred_env.cache_file(CACHE_NAME), ATTR, 45)

    truth = fred_env.ctl.series("UNRATE")
    assert out["U-3"].first_valid_index() == truth.index[0]


def test_incremental_total_failure_returns_the_cache_unchanged(fred_env, probe_service):
    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)
    cached = _build_stale_cache(cls, fred_env, MIXED, {"DGS10": "2026-03-31", "UNRATE": "2026-03-01"})
    mtime = cache_file.stat().st_mtime_ns
    fred_env.ctl.fail.update(MIXED.values())

    out = cls._get_group(MIXED, cache_file, ATTR, 45)

    _assert_frame(out, cached)
    assert len(fred_env.ctl.calls) == 2
    assert cache_file.stat().st_mtime_ns == mtime  # nothing new -> not rewritten
    assert isinstance(getattr(cls, ATTR), float)  # ... but the cooldown is armed


def test_no_api_key_with_stale_cache_returns_none(fred_env, probe_service, monkeypatch):
    """CURRENT behaviour: without a key the stale cache is discarded (None), not served."""
    from app.services.fred_api_key_service import FredApiKeyService

    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)
    _build_stale_cache(cls, fred_env, MIXED, {"DGS10": "2026-03-31", "UNRATE": "2026-03-01"})
    monkeypatch.setattr(FredApiKeyService, "_api_key", None)

    assert cls._get_group(MIXED, cache_file, ATTR, 45) is None
    assert fred_env.ctl.calls == []
    assert cache_file.exists()  # the file itself is left alone


# ── Cooldown ─────────────────────────────────────────────────────────────────


def test_fetch_cooldown_is_one_hour():
    assert BaseFredService._FETCH_COOLDOWN == 3600


def test_cooldown_serves_the_stale_cache_without_fetching(fred_env, probe_service, monkeypatch):
    cls = probe_service()
    cached = _build_stale_cache(cls, fred_env, MIXED, {"DGS10": "2026-03-31", "UNRATE": "2026-03-01"})
    armed_at = time.monotonic() - 10
    monkeypatch.setattr(cls, ATTR, armed_at, raising=False)
    instances = fred_env.ctl.instances

    out = cls._get_group(MIXED, fred_env.cache_file(CACHE_NAME), ATTR, 45)

    _assert_frame(out, cached)
    assert fred_env.ctl.calls == [] and fred_env.ctl.instances == instances  # no Fred client
    assert getattr(cls, ATTR) == armed_at  # not re-armed


def test_expired_cooldown_fetches_again(fred_env, probe_service, monkeypatch):
    cls = probe_service()
    _build_stale_cache(cls, fred_env, MIXED, {"DGS10": "2026-03-31", "UNRATE": "2026-03-01"})
    monkeypatch.setattr(cls, ATTR, time.monotonic() - cls._FETCH_COOLDOWN - 1, raising=False)

    out = cls._get_group(MIXED, fred_env.cache_file(CACHE_NAME), ATTR, 45)

    assert sorted(fred_env.ctl.calls) == [("DGS10", "2026-03-31", None), ("UNRATE", "2026-03-31", None)]
    assert out.index.max() == pd.Timestamp("2026-06-30")


def test_successful_incremental_fetch_also_starts_the_cooldown(fred_env, probe_service):
    """CURRENT behaviour: even a successful update blocks the next update for an hour
    (TreasuryFredService instead clears its cooldown when new rows arrived)."""
    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)
    _build_stale_cache(cls, fred_env, MIXED, {"DGS10": "2026-03-31", "UNRATE": "2026-03-01"})
    fred_env.ctl.end_dates.update({"DGS10": "2026-05-15", "UNRATE": "2026-05-01"})
    first = cls._get_group(MIXED, cache_file, ATTR, 45)
    assert first.index.max() == pd.Timestamp("2026-05-15")
    fred_env.ctl.end_dates.clear()
    fred_env.ctl.reset_calls()

    second = cls._get_group(MIXED, cache_file, ATTR, 45)  # newer data exists at FakeFred

    assert fred_env.ctl.calls == []
    _assert_frame(second, first)


# ── Cache file problems ──────────────────────────────────────────────────────


def test_corrupt_cache_is_deleted_and_refetched(fred_env, probe_service, caplog):
    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)
    fred_env.write_current_version()
    cache_file.write_bytes(b"_QT_TEST_ not a parquet file")

    with caplog.at_level(logging.WARNING):
        out = cls._get_group(MIXED, cache_file, ATTR, 45)

    assert f"Failed to read FRED cache {CACHE_NAME}" in caplog.text
    assert sorted(fred_env.ctl.calls) == [("DGS10", None, None), ("UNRATE", None, None)]
    _assert_frame(out, _truth_frame(fred_env.ctl, MIXED))
    _assert_frame(pd.read_parquet(cache_file), out)


@pytest.mark.parametrize("columns", [["_QT_TEST_unknown"], []])
def test_cache_without_known_columns_counts_as_missing(fred_env, probe_service, columns):
    cls = probe_service()
    cache_file = fred_env.cache_file(CACHE_NAME)
    if columns:
        _synthetic_cache(fred_env, cache_file, date.today(), columns)
    else:
        fred_env.write_current_version()
        pd.DataFrame(index=pd.DatetimeIndex([], name="Date")).to_parquet(cache_file)
    assert cache_file.exists()

    out = cls._get_group(MIXED, cache_file, ATTR, 45)

    assert sorted(fred_env.ctl.calls) == [("DGS10", None, None), ("UNRATE", None, None)]
    assert sorted(out.columns) == ["10Y", "U-3"]


# ── Declarative GROUPS -> fetch_all_data ─────────────────────────────────────


def _probe_groups():
    return [
        FredGroup(
            series={"10Y": "DGS10", "U-3": "UNRATE", "GDP": "GDPC1"},
            cache_file="_qt_test_probe_mixed.parquet",
            max_age_days=45,
            outputs=[
                FredOutput(key="rates", columns=["U-3", "10Y", "_QT_TEST_absent"]),
                FredOutput(key="gdp_tn", columns=["GDP"], unit_scale=1 / 1000),
                FredOutput(key="_qt_test_missing", columns=["_QT_TEST_absent"]),
            ],
        ),
        FredGroup(
            series={"USREC": "USREC"},
            cache_file="_qt_test_probe_usrec.parquet",
            max_age_days=7,
            outputs=[FredOutput(key="usrec", columns=["USREC"])],
        ),
    ]


def test_groups_fetch_all_data_builds_outputs(fred_env, probe_service, monkeypatch):
    cls = probe_service(groups=_probe_groups())
    seen = []
    real = BaseFredService._get_group.__func__

    def spy(klass, series_map, cache_file, fetch_attr, max_age_days=45):
        seen.append((dict(series_map), cache_file, fetch_attr, max_age_days))
        return real(klass, series_map, cache_file, fetch_attr, max_age_days)

    monkeypatch.setattr(cls, "_get_group", classmethod(spy))

    result = cls.fetch_all_data()

    assert sorted(result) == ["gdp_tn", "rates", "usrec"]  # output with no columns skipped
    assert [(s[1], s[2], s[3]) for s in seen] == [
        (fred_env.cache_dir / "_qt_test_probe_mixed.parquet", "_last_group_0_fetch", 45),
        (fred_env.cache_dir / "_qt_test_probe_usrec.parquet", "_last_group_1_fetch", 7),
    ]
    raw = _truth_frame(fred_env.ctl, {"10Y": "DGS10", "U-3": "UNRATE", "GDP": "GDPC1"})
    # declared column order (not fetch order), unknown columns dropped, all-NaN rows dropped
    assert list(result["rates"].columns) == ["U-3", "10Y"]
    pd.testing.assert_frame_equal(result["rates"], raw[["U-3", "10Y"]].dropna(how="all"),
                                  check_freq=False)
    pd.testing.assert_frame_equal(result["gdp_tn"], raw[["GDP"]].dropna(how="all") * (1 / 1000),
                                  check_freq=False)
    # the quarterly column rides on the daily/monthly union index (ffilled)
    gdp = fred_env.ctl.series("GDPC1")
    assert result["gdp_tn"].loc["2026-06-30", "GDP"] == pytest.approx(gdp.iloc[-1] / 1000)
    assert result["gdp_tn"].index.min() == gdp.index[0]
    usrec = fred_env.ctl.series("USREC")
    pd.testing.assert_series_equal(result["usrec"]["USREC"], usrec, check_names=False,
                                   check_freq=False)
    assert sorted(p.name for p in fred_env.cache_dir.glob("*.parquet")) == [
        "_qt_test_probe_mixed.parquet", "_qt_test_probe_usrec.parquet"]


def test_groups_fetch_all_data_returns_none_when_every_group_fails(fred_env, probe_service):
    cls = probe_service(groups=_probe_groups())
    fred_env.ctl.fail.update({"DGS10", "UNRATE", "GDPC1", "USREC"})

    assert cls.fetch_all_data() is None


def test_groups_fetch_all_data_keeps_the_groups_that_succeed(fred_env, probe_service):
    cls = probe_service(groups=_probe_groups())
    fred_env.ctl.fail.add("USREC")

    result = cls.fetch_all_data()

    assert sorted(result) == ["gdp_tn", "rates"]


def test_fetch_all_data_without_groups_raises(probe_service):
    cls = probe_service()
    with pytest.raises(NotImplementedError, match="must define GROUPS"):
        cls.fetch_all_data()


# ── Small helpers ────────────────────────────────────────────────────────────


def test_latest_value_helper():
    idx = pd.date_range("2026-01-01", periods=3, freq="MS")
    data = {"k": pd.DataFrame({"a": [1.23456, 2.34567, np.nan], "b": [np.nan] * 3}, index=idx)}
    assert BaseFredService._latest_value(data, "k", "a") == 2.35
    assert BaseFredService._latest_value(data, "k", "a", 0) == 2.0
    assert BaseFredService._latest_value(data, "k", "b") is None
    assert BaseFredService._latest_value(data, "k", "_QT_TEST_absent") is None
    assert BaseFredService._latest_value(data, "_QT_TEST_absent", "a") is None


def test_compute_yoy_helper():
    idx = pd.date_range("2024-01-01", periods=25, freq="MS")
    raw = pd.DataFrame({"x": np.arange(100.0, 125.0)}, index=idx)
    yoy = BaseFredService._compute_yoy(raw)
    assert yoy.index[0] == pd.Timestamp("2025-01-01") and len(yoy) == 13
    assert yoy.loc["2025-01-01", "x"] == pytest.approx(12.0)
    assert yoy.loc["2026-01-01", "x"] == pytest.approx((124.0 / 112.0 - 1) * 100)
    assert BaseFredService._compute_yoy(None).empty
    assert BaseFredService._compute_yoy(pd.DataFrame()).empty
