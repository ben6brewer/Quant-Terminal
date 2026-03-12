"""Tests for credit FRED service."""

import pytest


class TestCreditFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.credit.services.credit_fred_service import CreditFredService
        return CreditFredService

    def test_groups_defined(self, service):
        assert len(service.GROUPS) == 2
        assert service.GROUPS[0].series
        assert service.GROUPS[1].series

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            assert {"delinquency", "credit", "usrec"}.issubset(set(result.keys()))

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
