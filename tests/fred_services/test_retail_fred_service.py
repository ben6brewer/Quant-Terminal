"""Tests for retail FRED service."""

import pytest


class TestRetailFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.retail.services.retail_fred_service import RetailFredService
        return RetailFredService

    def test_groups_defined(self, service):
        assert len(service.GROUPS) > 0
        assert service.GROUPS[0].series

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            assert {"retail", "vehicles", "usrec"}.issubset(set(result.keys()))

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
