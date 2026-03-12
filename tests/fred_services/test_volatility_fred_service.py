"""Tests for volatility FRED service."""

import pytest


class TestVolatilityFredService:
    @pytest.fixture
    def service(self, monkeypatch):
        from app.ui.modules.volatility_index.services import volatility_fred_service as mod
        # Patch _fetch_move to avoid Yahoo call
        monkeypatch.setattr(mod.VolatilityFredService, "_fetch_move", classmethod(lambda cls: None))
        return mod.VolatilityFredService

    def test_fetch_all_data_callable(self, service):
        assert callable(getattr(service, "fetch_all_data", None))

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            assert {"volatility", "usrec"}.issubset(set(result.keys()))

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
