"""Local fixtures for ``tests/portfolio`` (P0.T7 characterization slice).

Goldens for this directory live in ``tests/portfolio/goldens/<area>/<name>.json``:
the tests use ``_helpers.assert_golden``, which is ``golden_utils.assert_golden``
with ``goldens_dir`` bound to that directory.  Everything else
(``--update-goldens``, canonicalization) is the shared harness.

Isolation:

* ``fresh_home`` (root conftest) gives each test its own short temp home, so
  ``PortfolioPersistence``, ``custom_data_service`` (``user_data_dir()``),
  ``MarketDataCache`` and ``ReturnsDataService`` all write under it.
* ``market_env`` adds the FakeYahoo patch and resets the in-memory caches of
  ``app.services.market_data`` and ``TickerMetadataService`` so every test sees
  the same cold-cache path (memory -> disk -> FakeYahoo).
"""

from __future__ import annotations

import pytest


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
