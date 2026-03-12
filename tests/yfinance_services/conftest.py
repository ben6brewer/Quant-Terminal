"""YFinance services conftest - autouse fixtures for cache isolation and class cache reset."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def isolate_metals_cache(tmp_path, monkeypatch):
    """Redirect metals cache paths to tmp_path."""
    from pathlib import Path

    tmp_yf = tmp_path / "yf_cache"
    tmp_yf.mkdir()

    from app.ui.modules.metals.services import metals_yfinance_service as mod

    monkeypatch.setattr(mod, "_CACHE_DIR", tmp_yf)
    monkeypatch.setattr(mod, "_METALS_CACHE", tmp_yf / "metals_futures.parquet")

    yield


@pytest.fixture(autouse=True)
def reset_metals_class_caches():
    """Reset class-level caches between tests."""
    yield
    try:
        from app.ui.modules.metals.services.metals_yfinance_service import MetalsYFinanceService
        MetalsYFinanceService._data = None
        MetalsYFinanceService._last_fetch = None
    except Exception:
        pass


@pytest.fixture
def mock_yfinance_download(monkeypatch):
    """Patch yfinance.download to return a synthetic MultiIndex DataFrame."""
    dates = pd.date_range("2020-01-01", periods=100, freq="B")
    tickers = ["GC=F", "SI=F", "HG=F", "PL=F", "PA=F"]

    # Build MultiIndex columns: (Price, Ticker)
    arrays = [
        ["Close"] * len(tickers),
        tickers,
    ]
    tuples = list(zip(*arrays))
    columns = pd.MultiIndex.from_tuples(tuples, names=["Price", "Ticker"])

    data = np.random.default_rng(42).uniform(50, 2000, size=(100, len(tickers)))
    df = pd.DataFrame(data, index=dates, columns=columns)

    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)
    return df
