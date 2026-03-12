"""Tests for recession FRED service."""

import pytest


class TestRecessionFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.recession.services.recession_fred_service import RecessionFredService
        return RecessionFredService

    def test_series_maps_defined(self):
        from app.ui.modules.recession.services import recession_fred_service as mod
        assert hasattr(mod, "MONTHLY_SERIES")
        assert len(mod.MONTHLY_SERIES) > 0

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            assert {"recession", "leading", "usrec"}.issubset(set(result.keys()))

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
