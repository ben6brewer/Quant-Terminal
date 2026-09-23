"""Local fixtures for ``tests/portfolio`` (P0.T7 characterization slice).

Goldens for this directory live in ``tests/portfolio/goldens/<area>/<name>.json``:
this slice owns only ``tests/portfolio/``, so ``golden_utils.GOLDENS_DIR`` is
re-pointed here for every test collected below this directory.  Everything else
(``assert_golden``, ``--update-goldens``, canonicalization) is the shared harness.

Isolation:

* ``fresh_home`` (root conftest) gives each test its own short temp home, so
  ``PortfolioPersistence``, ``custom_data_service`` (``user_data_dir()``),
  ``MarketDataCache`` and ``ReturnsDataService`` all write under it.
* ``market_env`` adds the FakeYahoo patch and resets the in-memory caches of
  ``app.services.market_data`` and ``TickerMetadataService`` so every test sees
  the same cold-cache path (memory -> disk -> FakeYahoo).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import golden_utils

LOCAL_GOLDENS_DIR: Path = Path(__file__).resolve().parent / "goldens"


@pytest.fixture(autouse=True)
def _portfolio_goldens_dir(monkeypatch):
    """Store/compare this directory's goldens under tests/portfolio/goldens/."""
    monkeypatch.setattr(golden_utils, "GOLDENS_DIR", LOCAL_GOLDENS_DIR)


@pytest.fixture
def market_env(fake_yahoo, fresh_home, monkeypatch):
    """FakeYahoo + a fresh home + empty market-data memory caches.

    Returns the :class:`FakeYahooController`.
    """
    import app.services.market_data as market_data
    from app.services.ticker_metadata_service import TickerMetadataService

    # raising=False: these are private caches that later refactors may rename; the
    # fakes are deterministic, so a missed reset can only cost speed, not results.
    monkeypatch.setattr(market_data, "_memory_cache", {}, raising=False)
    monkeypatch.setattr(market_data, "_live_bar_cache", {}, raising=False)
    monkeypatch.setattr(TickerMetadataService, "_cache", None, raising=False)
    return fake_yahoo
