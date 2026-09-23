"""Golden snapshots of ``fetch_all_data()`` for EVERY FRED service (P0.T1).

Services are discovered by importing every module under
``app.ui.modules.*.services`` and collecting the concrete ``BaseFredService``
subclasses (``fred_core_support.discover_fred_service_classes``); the
standalone ``TreasuryFredService.fetch_all_treasury_data`` is covered
separately.  Each golden holds a ``frame_digest`` per output key, the
``get_latest_stats`` result and the set of FRED ids requested.

Data comes from FakeFred (plus FakeYahoo for the MOVE index) and every
cache goes to a per-test home (``fresh_home``), so the goldens are
deterministic.  Goldens live in ``tests/goldens/fred_core/``; regenerate them
(``--update-goldens``) only in a ``Behavior-Change: yes`` commit.
"""

from __future__ import annotations

import concurrent.futures as cf
import shutil
from datetime import date

import pandas as pd
import pytest

import golden_utils
from fixtures.fake_fred import END_DATE
from fred_core.fred_core_support import (
    COMPLETION_ORDER_KEYS,
    GOLDEN_AREA,
    discover_fred_service_classes,
    output_digest,
    reset_fetch_cooldowns,
    service_snapshot,
)
from golden_utils import assert_golden, compare_canonical, canonicalize

SERVICE_CLASSES, IMPORT_ERRORS = discover_fred_service_classes()
_IDS = [c.__name__ for c in SERVICE_CLASSES]
_TREASURY = "TreasuryFredService"


def _golden_name(service_name: str) -> str:
    return f"fetch_all_{service_name}"


@pytest.fixture
def isolated_metadata_cache(monkeypatch):
    """VolatilityFredService pulls ^MOVE via Yahoo, which also caches ticker metadata."""
    from app.services.ticker_metadata_service import TickerMetadataService

    monkeypatch.setattr(TickerMetadataService, "_cache", None)


def _parquet_files(root):
    return sorted(p for p in root.rglob("*.parquet"))


def _digests(service_name, result):
    return canonicalize({k: output_digest(service_name, k, v) for k, v in result.items()})


def _treasury():
    from app.ui.modules.treasury.services.treasury_fred_service import TreasuryFredService

    return TreasuryFredService


# ── Discovery ────────────────────────────────────────────────────────────────


def test_discovery_imports_every_service_module_cleanly():
    assert IMPORT_ERRORS == {}


def test_discovery_finds_every_fred_service():
    names = [c.__name__ for c in SERVICE_CLASSES]
    assert len(names) == len(set(names)), "golden names are keyed by class name"
    assert len(names) >= 30
    for expected in ("UnemploymentAgeService", "GdpFredService", "LaborMarketFredService",
                     "InflationFredService", "MonetaryFredService", "VolatilityFredService",
                     "CreditFredService", "HomeMarketFredService"):
        assert expected in names
    assert _TREASURY not in names  # not a BaseFredService subclass (yet): covered below


def test_every_golden_file_belongs_to_a_discovered_service():
    """A deleted/renamed service must take its golden with it (and vice versa)."""
    gdir = golden_utils.GOLDENS_DIR / GOLDEN_AREA
    on_disk = {p.stem[len("fetch_all_"):] for p in gdir.glob("fetch_all_*.json")}
    expected = set(_IDS) | {_TREASURY}
    assert sorted(on_disk - expected) == []
    if not golden_utils.UPDATE:
        assert sorted(expected - on_disk) == []


# ── fetch_all_data goldens (one per service) ─────────────────────────────────


@pytest.mark.golden
@pytest.mark.parametrize("cls", SERVICE_CLASSES, ids=_IDS)
def test_fetch_all_data_golden(cls, fred_env, fake_yahoo, isolated_metadata_cache, monkeypatch):
    reset_fetch_cooldowns(monkeypatch, cls)

    result = cls.fetch_all_data()

    assert isinstance(result, dict) and result
    for key, obj in result.items():
        assert isinstance(obj, (pd.DataFrame, pd.Series)), key
        assert not obj.empty, key
        assert isinstance(obj.index, pd.DatetimeIndex), key
        assert obj.index.is_monotonic_increasing and obj.index.is_unique, key
        assert obj.index.max() <= END_DATE, key
    # No cache existed, so every series was fetched with its full history ...
    assert fred_env.ctl.calls and all(start is None for _, start, _ in fred_env.ctl.calls)
    # ... and the parquet caches went to this test's temp home.
    assert _parquet_files(fred_env.home)

    snap = service_snapshot(cls, result, fred_env.ctl.call_ids())
    assert_golden(_golden_name(cls.__name__), snap, area=GOLDEN_AREA)


@pytest.mark.parametrize("cls", SERVICE_CLASSES, ids=_IDS)
def test_refetch_from_stale_cache_reproduces_outputs(cls, fred_env, fake_yahoo,
                                                     isolated_metadata_cache, monkeypatch):
    """Second call (cache present but stale vs. the real clock) never re-downloads full
    history and - with no new FRED data - returns exactly the same outputs."""
    reset_fetch_cooldowns(monkeypatch, cls)
    first = _digests(cls.__name__, cls.fetch_all_data())
    fred_env.ctl.reset_calls()

    second = cls.fetch_all_data()

    assert compare_canonical(_digests(cls.__name__, second), first) == []
    assert all(start is not None for _, start, _ in fred_env.ctl.calls), fred_env.ctl.calls


# ── TreasuryFredService (standalone copy of the base logic) ─────────────────


@pytest.mark.golden
def test_treasury_fetch_all_treasury_data_golden(fred_env, monkeypatch):
    svc = _treasury()
    monkeypatch.setattr(svc, "_last_fetch_time", None)

    df = svc.fetch_all_treasury_data()

    assert isinstance(df, pd.DataFrame) and not df.empty
    assert df.index.max() == END_DATE
    assert all(start is None for _, start, _ in fred_env.ctl.calls)
    import app.ui.modules.treasury.services.treasury_fred_service as tmod

    assert tmod.CACHE_FILE.is_relative_to(fred_env.home) and tmod.CACHE_FILE.exists()

    sunday = date(2026, 6, 14)
    snap = {
        "service": _TREASURY,
        "outputs": {"treasury": output_digest(_TREASURY, "treasury", df)},
        "latest_yields": svc.get_latest_yields(df),
        "yields_for_2026-06-14": svc.get_yields_for_date(df, sunday),
        "actual_date_for_2026-06-14": svc.get_actual_date(df, sunday),
        "yields_for_1900-01-01": svc.get_yields_for_date(df, date(1900, 1, 1)),
        "fred_ids": sorted(set(fred_env.ctl.call_ids())),
    }
    assert snap["actual_date_for_2026-06-14"] == date(2026, 6, 12)  # ffill to Friday
    assert_golden(_golden_name(_TREASURY), snap, area=GOLDEN_AREA)


def test_treasury_refetch_from_stale_cache_reproduces_output(fred_env, monkeypatch):
    svc = _treasury()
    monkeypatch.setattr(svc, "_last_fetch_time", None)
    first = canonicalize(output_digest(_TREASURY, "treasury", svc.fetch_all_treasury_data()))
    fred_env.ctl.reset_calls()

    second = svc.fetch_all_treasury_data()

    assert compare_canonical(canonicalize(output_digest(_TREASURY, "treasury", second)), first) == []
    assert fred_env.ctl.calls
    assert {start for _, start, _ in fred_env.ctl.calls} == {"2026-06-30"}


# ── Column-order determinism ─────────────────────────────────────────────────


def _ordered_as_completed(reverse: bool):
    def fake(fs, timeout=None):
        futures = list(fs)
        return futures[::-1] if reverse else futures

    return fake


def test_completion_order_allowlist_is_complete(fred_env, fake_yahoo, isolated_metadata_cache,
                                                monkeypatch):
    """Only the outputs in COMPLETION_ORDER_KEYS may change column order with the
    thread completion order; every other golden keeps its real column order."""
    orders = {}
    for reverse in (False, True):
        monkeypatch.setattr(cf, "as_completed", _ordered_as_completed(reverse))
        for cls in SERVICE_CLASSES:
            reset_fetch_cooldowns(monkeypatch, cls)
            shutil.rmtree(fred_env.cache_dir, ignore_errors=True)
            for key, obj in cls.fetch_all_data().items():
                cols = list(obj.columns) if isinstance(obj, pd.DataFrame) else [obj.name]
                orders.setdefault((cls.__name__, key), []).append(cols)
        svc = _treasury()
        monkeypatch.setattr(svc, "_last_fetch_time", None)
        shutil.rmtree(fred_env.cache_dir, ignore_errors=True)
        orders.setdefault((_TREASURY, "treasury"), []).append(
            list(svc.fetch_all_treasury_data().columns))

    unstable = {k for k, (fwd, rev) in orders.items() if fwd != rev}
    assert sorted(unstable - COMPLETION_ORDER_KEYS) == []
    # every allow-listed key is a real output (keeps the list honest)
    assert sorted(COMPLETION_ORDER_KEYS - set(orders)) == []


def test_groups_outputs_follow_declared_column_order(fred_env, monkeypatch):
    """GROUPS-based outputs are ordered by ``FredOutput.columns``, never by fetch order."""
    monkeypatch.setattr(cf, "as_completed", _ordered_as_completed(True))
    checked = 0
    for cls in SERVICE_CLASSES:
        if not cls.GROUPS or "fetch_all_data" in vars(cls):
            continue
        reset_fetch_cooldowns(monkeypatch, cls)
        result = cls.fetch_all_data()
        for group in cls.GROUPS:
            for out in group.outputs:
                if out.key in result:
                    assert list(result[out.key].columns) == [
                        c for c in out.columns if c in result[out.key].columns
                    ], (cls.__name__, out.key)
                    checked += 1
    assert checked >= 40
