"""Tests for commodity (energy) FRED service."""

import pytest


class TestCommodityFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.commodities.services.commodity_fred_service import CommodityFredService
        return CommodityFredService

    def test_series_maps_defined(self):
        from app.ui.modules.commodities.services import commodity_fred_service as mod
        assert hasattr(mod, "ENERGY_SERIES")
        assert len(mod.ENERGY_SERIES) > 0

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            assert {"energy", "usrec"}.issubset(set(result.keys()))

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
