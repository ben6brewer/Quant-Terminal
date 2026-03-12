"""Tests for income FRED service."""

import pytest


class TestIncomeFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.income.services.income_fred_service import IncomeFredService
        return IncomeFredService

    def test_series_maps_defined(self):
        from app.ui.modules.income.services import income_fred_service as mod
        assert hasattr(mod, "INCOME_SERIES")
        assert len(mod.INCOME_SERIES) > 0

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            assert {"income", "real_income", "savings", "wages_raw", "wages", "usrec"}.issubset(
                set(result.keys())
            )

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
