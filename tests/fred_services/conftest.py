"""FRED services conftest - autouse fixture to reset class-level caches."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def isolate_fred_cache(tmp_path, monkeypatch):
    """Redirect ALL FRED cache file paths to tmp_path so tests never touch the real cache."""
    from pathlib import Path

    tmp_fred = tmp_path / "fred_cache"
    tmp_fred.mkdir()

    # Patch module-level cache constants in every FRED service module.
    # Services migrated to GROUPS use base_fred_service.CACHE_DIR only.
    _modules_and_attrs = [
        ("app.services.base_fred_service", ["CACHE_DIR", "_FRED_VERSION_FILE"]),
        (
            "app.ui.modules.inflation.services.inflation_fred_service",
            ["_CACHE_DIR", "CPI_CACHE_FILE", "PCE_CACHE_FILE", "PPI_CACHE_FILE", "EXPECTATIONS_CACHE_FILE"],
        ),
        (
            "app.ui.modules.monetary_policy.services.monetary_fred_service",
            ["_CACHE_DIR", "_MONTHLY_CACHE", "_WEEKLY_CACHE", "_EFFR_CACHE"],
        ),
        (
            "app.ui.modules.labor_market.services.labor_market_fred_service",
            ["_CACHE_DIR", "MONTHLY_CACHE_FILE", "WEEKLY_CACHE_FILE"],
        ),
        (
            "app.ui.modules.treasury.services.treasury_fred_service",
            ["CACHE_DIR", "CACHE_FILE"],
        ),
        (
            "app.ui.modules.gdp.services.gdp_fred_service",
            ["_CACHE_DIR", "_QUARTERLY_CACHE", "_PRODUCTION_CACHE"],
        ),
        (
            "app.ui.modules.housing.services.housing_fred_service",
            ["_CACHE_DIR", "_HOUSING_CACHE"],
        ),
        (
            "app.ui.modules.recession.services.recession_fred_service",
            ["_CACHE_DIR", "_MONTHLY_CACHE"],
        ),
        (
            "app.ui.modules.financial_conditions.services.financial_conditions_fred_service",
            ["_CACHE_DIR", "_FINCOND_CACHE"],
        ),
        (
            "app.ui.modules.income.services.income_fred_service",
            ["_CACHE_DIR", "_INCOME_CACHE"],
        ),
    ]

    for mod_path, attrs in _modules_and_attrs:
        try:
            mod = __import__(mod_path, fromlist=attrs)
            for attr in attrs:
                orig = getattr(mod, attr, None)
                if orig is None:
                    continue
                if isinstance(orig, Path) and (orig.suffix or orig.name.startswith(".")):
                    # It's a file path — redirect to tmp_fred / filename
                    monkeypatch.setattr(mod, attr, tmp_fred / orig.name)
                else:
                    # It's a directory path
                    monkeypatch.setattr(mod, attr, tmp_fred)
        except Exception:
            pass

    yield


# Registry of all FRED service classes and their cache attributes to reset
_FRED_SERVICE_CLASSES = [
    ("app.ui.modules.inflation.services.inflation_fred_service", "InflationFredService"),
    ("app.ui.modules.monetary_policy.services.monetary_fred_service", "MonetaryFredService"),
    ("app.ui.modules.labor_market.services.labor_market_fred_service", "LaborMarketFredService"),
    ("app.ui.modules.treasury.services.treasury_fred_service", "TreasuryFredService"),
    ("app.ui.modules.gdp.services.gdp_fred_service", "GdpFredService"),
    ("app.ui.modules.housing.services.housing_fred_service", "HousingFredService"),
    ("app.ui.modules.consumer.services.consumer_fred_service", "ConsumerFredService"),
    ("app.ui.modules.banking.services.banking_fred_service", "BankingFredService"),
    ("app.ui.modules.volatility_index.services.volatility_fred_service", "VolatilityFredService"),
    ("app.ui.modules.stress.services.stress_fred_service", "StressFredService"),
    ("app.ui.modules.recession.services.recession_fred_service", "RecessionFredService"),
    ("app.ui.modules.household.services.household_fred_service", "HouseholdFredService"),
    ("app.ui.modules.productivity_service.services.productivity_fred_service", "ProductivityFredService"),
    ("app.ui.modules.currency.services.currency_fred_service", "CurrencyFredService"),
    ("app.ui.modules.commodities.services.commodity_fred_service", "CommodityFredService"),
    ("app.ui.modules.retail.services.retail_fred_service", "RetailFredService"),
    ("app.ui.modules.mortgage.services.mortgage_fred_service", "MortgageFredService"),
    ("app.ui.modules.financial_conditions.services.financial_conditions_fred_service", "FinancialConditionsFredService"),
    ("app.ui.modules.trade.services.trade_fred_service", "TradeFredService"),
    ("app.ui.modules.credit.services.credit_fred_service", "CreditFredService"),
    ("app.ui.modules.fiscal.services.fiscal_fred_service", "FiscalFredService"),
    ("app.ui.modules.income.services.income_fred_service", "IncomeFredService"),
    ("app.ui.modules.manufacturing.services.manufacturing_fred_service", "ManufacturingFredService"),
]


@pytest.fixture(autouse=True)
def reset_fred_class_caches():
    """Reset class-level _data cache on all FRED services between tests."""
    yield
    for mod_path, cls_name in _FRED_SERVICE_CLASSES:
        try:
            mod = __import__(mod_path, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            cls._data = None
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
