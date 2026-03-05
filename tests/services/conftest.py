"""Services conftest - sample data fixtures and common mocks."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv_df():
    """252-day OHLCV DataFrame with realistic random-walk prices (seeded)."""
    rng = np.random.default_rng(42)
    n = 252
    dates = pd.bdate_range("2024-01-02", periods=n)

    # Geometric random walk starting at $100
    log_returns = rng.normal(0.0003, 0.015, n)
    close = 100.0 * np.exp(np.cumsum(log_returns))
    high = close * (1 + rng.uniform(0.001, 0.02, n))
    low = close * (1 - rng.uniform(0.001, 0.02, n))
    open_ = low + rng.uniform(0.3, 0.7, n) * (high - low)
    volume = rng.integers(1_000_000, 50_000_000, n)

    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


@pytest.fixture
def sample_returns_series():
    """504-day daily returns series (seeded)."""
    rng = np.random.default_rng(42)
    n = 504
    dates = pd.bdate_range("2023-01-02", periods=n)
    returns = rng.normal(0.0003, 0.015, n)
    return pd.Series(returns, index=dates, name="returns")


@pytest.fixture
def sample_benchmark_returns():
    """504-day benchmark returns series (seeded, different stream)."""
    rng = np.random.default_rng(123)
    n = 504
    dates = pd.bdate_range("2023-01-02", periods=n)
    returns = rng.normal(0.0004, 0.012, n)
    return pd.Series(returns, index=dates, name="benchmark")


@pytest.fixture
def mock_yahoo_download(monkeypatch):
    """Patch yfinance.download to return sample OHLCV data."""
    rng = np.random.default_rng(99)
    n = 100
    dates = pd.bdate_range("2024-06-01", periods=n)
    close = 150.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))

    mock_df = pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": rng.integers(1_000_000, 10_000_000, n),
        },
        index=dates,
    )

    def _download(*args, **kwargs):
        tickers = kwargs.get("tickers", args[0] if args else "")
        if isinstance(tickers, str) and " " in tickers:
            # Multi-ticker: return MultiIndex columns
            ticker_list = tickers.split()
            arrays = []
            for t in ticker_list:
                arrays.append(mock_df.copy())
            result = pd.concat(arrays, axis=1, keys=ticker_list)
            return result
        return mock_df.copy()

    monkeypatch.setattr("yfinance.download", _download)
    return mock_df


@pytest.fixture
def mock_fred_api(monkeypatch):
    """Patch fredapi.Fred to return sample time series data."""
    from unittest.mock import MagicMock

    dates = pd.date_range("2020-01-01", periods=60, freq="MS")
    sample_data = pd.Series(
        np.linspace(250, 300, 60),
        index=dates,
    )

    mock_fred = MagicMock()
    mock_fred.get_series.return_value = sample_data

    def _mock_fred_init(*args, **kwargs):
        return mock_fred

    monkeypatch.setattr("fredapi.Fred", _mock_fred_init)
    return mock_fred
