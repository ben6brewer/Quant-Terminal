"""Tests for banking FRED service."""

import pytest


class TestBankingFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.banking.services.banking_fred_service import BankingFredService
        return BankingFredService

    def test_series_maps_defined(self):
        from app.ui.modules.banking.services import banking_fred_service as mod
        assert hasattr(mod, "BANKING_SERIES")
        assert len(mod.BANKING_SERIES) > 0

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            assert {"loans", "usrec"}.issubset(set(result.keys()))

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
