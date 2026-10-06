"""Fixtures for the chart-module characterization tests (P0.T8).

* ``indicator_service`` - :class:`IndicatorService` with EMPTY in-memory
  registries, ``_initialized=False`` and every ``~/.quant_terminal`` path
  re-rooted into a per-test ``fresh_home``.  Plugin loading side effects
  (``sys.path`` insert, ``sys.modules`` entries) are undone at teardown.
* ``restart_indicators`` - callable that simulates an app restart: drops the
  in-memory registries and re-runs ``IndicatorService.initialize()`` so that
  everything is re-read from disk.
* ``ohlcv`` - deterministic daily OHLCV frame (FakeYahoo history of the
  ``_QT_TEST_OHLCV`` ticker, last 520 bars) with two flat candles
  (Close == Open) so every Volume direction value (-1, 0, 1) occurs.
* ``chart_golden`` - ``assert_golden`` bound to ``tests/chart/goldens/<area>``
  (kept inside this slice's directory; same canonical format and the same
  ``--update-goldens`` switch as ``tests/golden_utils.py``).
* ``stub_plugin_preview_data`` - serves ``fetch_price_history`` (used today by
  plugin column previews) from the deterministic frame, never the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

CHART_TESTS_DIR = Path(__file__).resolve().parent
CHART_GOLDENS_DIR = CHART_TESTS_DIR / "goldens"

# Plugin modules that IndicatorService.load_custom_indicator_plugins registers
# in sys.modules by bare file stem.
_PLUGIN_MODULE_NAMES = ("death_golden_cross", "base_indicator")

_REGISTRY_ATTRS = (
    "OVERLAY_INDICATORS",
    "OSCILLATOR_INDICATORS",
    "ALL_INDICATORS",
    "CUSTOM_INDICATOR_CLASSES",
    "PLUGIN_APPEARANCE_OVERRIDES",
)

OHLCV_TICKER = "_QT_TEST_OHLCV"
OHLCV_BARS = 520
FLAT_BAR_POSITIONS = (37, 211)


def _reset_registry(svc, monkeypatch) -> None:
    for attr in _REGISTRY_ATTRS:
        monkeypatch.setattr(svc, attr, {})
    monkeypatch.setattr(svc, "_initialized", False)


@pytest.fixture
def indicator_service(fresh_home, monkeypatch):
    """IndicatorService class with empty registries and a fresh, empty home."""
    from app.ui.modules.chart.services.indicator_service import IndicatorService as svc

    for attr in ("_SAVE_PATH", "_PLUGIN_APPEARANCE_PATH", "_VOLUME_SETTINGS_PATH"):
        path = Path(getattr(svc, attr))
        assert fresh_home in path.parents, f"IndicatorService.{attr}={path} is not under {fresh_home}"

    _reset_registry(svc, monkeypatch)
    monkeypatch.setattr(svc, "_PLUGIN_PATH", svc._PLUGIN_PATH)
    monkeypatch.setattr(sys, "path", list(sys.path))
    preexisting = {name: sys.modules.get(name) for name in _PLUGIN_MODULE_NAMES}
    yield svc
    for name, mod in preexisting.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


@pytest.fixture
def restart_indicators(indicator_service, monkeypatch):
    """Return ``restart()``: forget in-memory state, re-initialize from disk."""

    def restart():
        _reset_registry(indicator_service, monkeypatch)
        indicator_service.initialize()
        return indicator_service

    return restart


@pytest.fixture(scope="session")
def _ohlcv_master():
    from fixtures.fake_yahoo import generate_history

    df = generate_history(OHLCV_TICKER).tail(OHLCV_BARS)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    for pos in FLAT_BAR_POSITIONS:
        df.iloc[pos, df.columns.get_loc("Close")] = df.iloc[pos, df.columns.get_loc("Open")]
    return df


@pytest.fixture
def ohlcv(_ohlcv_master):
    """Deterministic OHLCV frame (fresh copy per test)."""
    return _ohlcv_master.copy()


@pytest.fixture
def chart_golden():
    """``assert_golden`` writing/reading ``tests/chart/goldens/<area>/<name>.json``."""
    import golden_utils

    def check(name, data, area="indicators", **kwargs):
        golden_utils.assert_golden(name, data, area=area, goldens_dir=CHART_GOLDENS_DIR, **kwargs)

    return check


@pytest.fixture
def stub_plugin_preview_data(monkeypatch, ohlcv):
    """Serve ``app.services.market_data.fetch_price_history`` from ``ohlcv``.

    Today ``IndicatorService.preview_indicator_columns`` fetches BTC-USD history
    just to learn a plugin's output columns; this keeps that offline and
    independent of the market-data caches.  Returns the list of calls.
    """
    import app.services.market_data as market_data

    calls = []

    def fake_fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=False):
        calls.append((ticker, period, interval))
        return ohlcv.copy()

    monkeypatch.setattr(market_data, "fetch_price_history", fake_fetch_price_history)
    return calls
