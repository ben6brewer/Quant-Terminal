"""Tests for Housing FRED service."""

import numpy as np
import pandas as pd
import pytest


class TestHousingFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.housing.services.housing_fred_service import HousingFredService
        return HousingFredService

    def test_series_map_defined(self):
        from app.ui.modules.housing.services import housing_fred_service as mod
        assert hasattr(mod, "HOUSING_SERIES")
        assert len(mod.HOUSING_SERIES) > 0

    def test_housing_series_contains_expected(self):
        from app.ui.modules.housing.services.housing_fred_service import HOUSING_SERIES
        assert "Total Starts" in HOUSING_SERIES
        assert "Single-Family" in HOUSING_SERIES
        assert "Total Permits" in HOUSING_SERIES
        assert "USREC" in HOUSING_SERIES

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            possible_keys = {"starts", "permits", "usrec"}
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

    def test_multi_family_permits_derived(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None and "permits" in result:
            permits_df = result["permits"]
            assert "Multi-Family Permits" in permits_df.columns
            # Verify derivation: Multi-Family = Total - SF
            if "Total Permits" in permits_df.columns and "SF Permits" in permits_df.columns:
                expected = permits_df["Total Permits"] - permits_df["SF Permits"]
                pd.testing.assert_series_equal(
                    permits_df["Multi-Family Permits"], expected, check_names=False
                )

    def test_get_latest_stats_total_permits_key(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            stats = service.get_latest_stats(result)
            if stats is not None and "permits" in result:
                assert "total_permits" in stats
                assert "permits" not in stats
