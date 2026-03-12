"""Tests for metals yfinance service."""

import pytest


class TestMetalsYFinanceService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.metals.services.metals_yfinance_service import MetalsYFinanceService
        return MetalsYFinanceService

    def test_tickers_defined(self):
        from app.ui.modules.metals.services.metals_yfinance_service import TICKERS
        assert len(TICKERS) == 5
        assert TICKERS["GC=F"] == "Gold"
        assert TICKERS["SI=F"] == "Silver"
        assert TICKERS["HG=F"] == "Copper"
        assert TICKERS["PL=F"] == "Platinum"
        assert TICKERS["PA=F"] == "Palladium"

    def test_fetch_all_data_returns_dict(self, service, mock_yfinance_download):
        result = service.fetch_all_data()
        assert result is not None
        assert isinstance(result, dict)
        assert "metals" in result

    def test_metals_columns(self, service, mock_yfinance_download):
        result = service.fetch_all_data()
        metals_df = result["metals"]
        for col in ["Gold", "Silver", "Copper", "Platinum", "Palladium"]:
            assert col in metals_df.columns

    def test_get_latest_stats(self, service, mock_yfinance_download):
        result = service.fetch_all_data()
        stats = service.get_latest_stats(result)
        assert isinstance(stats, dict)
        assert "gold" in stats
        assert "silver" in stats

    def test_get_latest_stats_none(self, service):
        stats = service.get_latest_stats(None)
        assert stats is None

    def test_repeated_calls_use_cache(self, service, mock_yfinance_download):
        result1 = service.fetch_all_data()
        result2 = service.fetch_all_data()
        # Second call should return cached data (same object)
        assert result1 is result2

    def test_disk_cache_created(self, service, mock_yfinance_download, tmp_path):
        from app.ui.modules.metals.services import metals_yfinance_service as mod
        service.fetch_all_data()
        assert mod._METALS_CACHE.exists()
