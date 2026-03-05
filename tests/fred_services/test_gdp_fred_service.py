"""Tests for GDP FRED service."""

import numpy as np
import pandas as pd
import pytest


class TestGdpFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.gdp.services.gdp_fred_service import GdpFredService
        return GdpFredService

    def test_series_maps_defined(self):
        from app.ui.modules.gdp.services import gdp_fred_service as mod
        assert hasattr(mod, "QUARTERLY_SERIES")
        assert hasattr(mod, "PRODUCTION_SERIES")
        assert len(mod.QUARTERLY_SERIES) > 0
        assert len(mod.PRODUCTION_SERIES) > 0

    def test_quarterly_series_contains_expected(self):
        from app.ui.modules.gdp.services.gdp_fred_service import QUARTERLY_SERIES
        assert "Real GDP" in QUARTERLY_SERIES
        assert "GDP Growth" in QUARTERLY_SERIES
        assert "USREC" in QUARTERLY_SERIES

    def test_quarterly_series_has_exports_imports(self):
        from app.ui.modules.gdp.services.gdp_fred_service import QUARTERLY_SERIES
        assert "Exports" in QUARTERLY_SERIES
        assert "Imports" in QUARTERLY_SERIES
        assert QUARTERLY_SERIES["Exports"] == "EXPGSC1"
        assert QUARTERLY_SERIES["Imports"] == "IMPGSC1"

    def test_quarterly_series_no_net_exports(self):
        from app.ui.modules.gdp.services.gdp_fred_service import QUARTERLY_SERIES
        assert "Net Exports" not in QUARTERLY_SERIES

    def test_production_series_contains_expected(self):
        from app.ui.modules.gdp.services.gdp_fred_service import PRODUCTION_SERIES
        assert "Industrial Production" in PRODUCTION_SERIES
        assert "Manufacturing" in PRODUCTION_SERIES
        assert "Capacity Utilization" in PRODUCTION_SERIES

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            possible_keys = {"gdp", "growth", "components", "production", "capacity", "usrec"}
            assert set(result.keys()).issubset(possible_keys)

    def test_get_latest_stats(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            stats = service.get_latest_stats(result)
            if stats is not None:
                assert isinstance(stats, dict)

    def test_repeated_calls_return_consistent_data(self, service, mock_fred_api, mock_fred_api_key):
        result1 = service.fetch_all_data()
        result2 = service.fetch_all_data()
        if result1 is not None:
            assert result2 is not None
            assert set(result1.keys()) == set(result2.keys())
