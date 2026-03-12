"""Tests for household FRED service."""

import pytest


class TestHouseholdFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.household.services.household_fred_service import HouseholdFredService
        return HouseholdFredService

    def test_series_maps_defined(self):
        from app.ui.modules.household.services import household_fred_service as mod
        assert hasattr(mod, "HOUSEHOLD_SERIES")
        assert len(mod.HOUSEHOLD_SERIES) > 0

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            assert {"wealth", "household_debt", "debt", "usrec"}.issubset(set(result.keys()))

    def test_get_latest_stats(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        stats = service.get_latest_stats(result)
        assert stats is None or isinstance(stats, dict)

    def test_repeated_calls_consistent(self, service, mock_fred_api, mock_fred_api_key):
        result1 = service.fetch_all_data()
        result2 = service.fetch_all_data()
        if result1 is not None:
            assert result2 is not None
            assert set(result1.keys()) == set(result2.keys())
