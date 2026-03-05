"""FRED services conftest - autouse fixture to reset class-level caches."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def reset_fred_class_caches():
    """Reset class-level _data cache on all FRED services between tests."""
    yield
    # Reset after each test
    try:
        from app.ui.modules.inflation.services.inflation_fred_service import (
            InflationFredService,
        )
        InflationFredService._data = None
    except Exception:
        pass

    try:
        from app.ui.modules.monetary_policy.services.monetary_fred_service import (
            MonetaryFredService,
        )
        MonetaryFredService._data = None
    except Exception:
        pass

    try:
        from app.ui.modules.labor_market.services.labor_market_fred_service import (
            LaborMarketFredService,
        )
        LaborMarketFredService._data = None
    except Exception:
        pass

    try:
        from app.ui.modules.treasury.services.treasury_fred_service import (
            TreasuryFredService,
        )
        TreasuryFredService._data = None
    except Exception:
        pass


@pytest.fixture
def mock_fred_api(monkeypatch):
    """Patch fredapi.Fred to return sample time series data."""
    from unittest.mock import MagicMock

    dates = pd.date_range("2020-01-01", periods=60, freq="MS")
    sample_data = pd.Series(np.linspace(250, 300, 60), index=dates)

    mock_fred = MagicMock()
    mock_fred.get_series.return_value = sample_data

    def _mock_fred_init(*args, **kwargs):
        return mock_fred

    monkeypatch.setattr("fredapi.Fred", _mock_fred_init)
    return mock_fred


@pytest.fixture
def mock_fred_api_key(monkeypatch):
    """Ensure FRED API key is always available in tests."""
    monkeypatch.setattr(
        "app.services.fred_api_key_service.FredApiKeyService.get_api_key",
        lambda: "test_api_key",
    )
