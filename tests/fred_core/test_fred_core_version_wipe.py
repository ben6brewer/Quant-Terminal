"""Characterization of the one-time FRED cache version wipe (P0.T1).

``_check_fred_cache_version()`` runs once per process (module flag
``_version_checked``): when ``<cache>/.fred_cache_version`` is missing or
differs from ``_FRED_CACHE_VERSION`` it deletes every ``*.parquet`` directly
in the FRED cache dir and writes the current version.  ``fred_env`` re-arms
the flag and points the cache at a per-test home.
"""

from __future__ import annotations

import pandas as pd

import app.services.base_fred_service as base


def _seed_cache(env, names=("_qt_test_a.parquet", "_qt_test_b.parquet")):
    env.cache_dir.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2026-01-01", periods=3, freq="D", name="Date")
    for name in names:
        pd.DataFrame({"x": [1.0, 2.0, 3.0]}, index=idx).to_parquet(env.cache_dir / name)
    keep = env.cache_dir / "_qt_test_keep.json"
    keep.write_text("{}")
    nested = env.cache_dir / "_qt_test_sub"
    nested.mkdir(exist_ok=True)
    pd.DataFrame({"x": [1.0]}, index=idx[:1]).to_parquet(nested / "_qt_test_nested.parquet")
    return keep, nested / "_qt_test_nested.parquet"


def test_version_constants_and_location(fred_env):
    assert base._FRED_CACHE_VERSION == "2"
    assert fred_env.version_file == fred_env.cache_dir / ".fred_cache_version"
    assert fred_env.cache_dir == fred_env.home / ".quant_terminal" / "cache" / "fred"


def test_first_check_creates_dir_and_writes_version(fred_env):
    assert not fred_env.cache_dir.exists()

    base._check_fred_cache_version()

    assert fred_env.version_file.read_text() == "2"
    assert base._version_checked is True


def test_missing_version_file_wipes_top_level_parquet_only(fred_env, caplog):
    keep, nested = _seed_cache(fred_env)

    with caplog.at_level("INFO"):
        base._check_fred_cache_version()

    assert sorted(p.name for p in fred_env.cache_dir.glob("*.parquet")) == []
    assert keep.exists() and nested.exists()  # non-parquet files and sub-dirs survive
    assert fred_env.version_file.read_text() == "2"
    assert "deleted 2 parquet files" in caplog.text


def test_mismatched_version_wipes(fred_env):
    _seed_cache(fred_env)
    fred_env.version_file.write_text("1\n")

    base._check_fred_cache_version()

    assert list(fred_env.cache_dir.glob("*.parquet")) == []
    assert fred_env.version_file.read_text() == "2"


def test_matching_version_keeps_the_cache(fred_env):
    _seed_cache(fred_env)
    fred_env.version_file.write_text(" 2 \n")  # compared after strip()

    base._check_fred_cache_version()

    assert len(list(fred_env.cache_dir.glob("*.parquet"))) == 2
    assert fred_env.version_file.read_text() == " 2 \n"
    assert base._version_checked is True


def test_check_runs_only_once_per_process(fred_env):
    base._check_fred_cache_version()
    _seed_cache(fred_env)
    fred_env.version_file.write_text("1")

    base._check_fred_cache_version()  # flag already set -> no wipe

    assert len(list(fred_env.cache_dir.glob("*.parquet"))) == 2
    assert fred_env.version_file.read_text() == "1"


def test_get_group_checks_the_version_before_reading_the_cache(fred_env, probe_service):
    """A fresh-looking cache from an old version is wiped and fully re-fetched."""
    from datetime import date

    cls = probe_service()
    cache_file = fred_env.cache_file("_qt_test_versioned.parquet")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range(end=pd.Timestamp(date.today()), periods=3, freq="D", name="Date")
    pd.DataFrame({"U-3": [1.0, 2.0, 3.0]}, index=idx).to_parquet(cache_file)
    fred_env.version_file.write_text("1")

    out = cls._get_group({"U-3": "UNRATE"}, cache_file, "_last_probe_fetch", 45)

    assert fred_env.ctl.calls == [("UNRATE", None, None)]
    assert out.index.max() == pd.Timestamp("2026-06-01")
    assert fred_env.version_file.read_text() == "2"
