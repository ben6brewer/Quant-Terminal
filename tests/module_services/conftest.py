"""Module services conftest - shared fixtures for module-level service tests."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_returns_df():
    """Multi-ticker returns DataFrame for portfolio analysis tests."""
    rng = np.random.default_rng(42)
    n = 504
    dates = pd.bdate_range("2023-01-02", periods=n)
    return pd.DataFrame(
        {
            "AAPL": rng.normal(0.0005, 0.018, n),
            "MSFT": rng.normal(0.0004, 0.016, n),
            "GOOGL": rng.normal(0.0003, 0.020, n),
            "AMZN": rng.normal(0.0006, 0.022, n),
            "SPY": rng.normal(0.0004, 0.011, n),
        },
        index=dates,
    )


@pytest.fixture
def sample_weights():
    """Equal-weighted portfolio weights."""
    return {"AAPL": 0.2, "MSFT": 0.2, "GOOGL": 0.2, "AMZN": 0.2, "SPY": 0.2}


@pytest.fixture
def sample_prices_df():
    """Multi-ticker price DataFrame for module service tests."""
    rng = np.random.default_rng(42)
    n = 504
    dates = pd.bdate_range("2023-01-02", periods=n)
    base = {"AAPL": 150.0, "MSFT": 280.0, "GOOGL": 120.0}
    df = pd.DataFrame(index=dates)
    for ticker, start_price in base.items():
        log_returns = rng.normal(0.0003, 0.015, n)
        df[ticker] = start_price * np.exp(np.cumsum(log_returns))
    return df
