"""Tests for app.services.ticker_metadata_service.TickerMetadataService."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.ticker_metadata_service import TickerMetadataService


class TestTickerMetadataService:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        TickerMetadataService._cache = None
        yield
        TickerMetadataService._cache = None

    def test_get_sector_from_cache(self, monkeypatch):
        TickerMetadataService._cache = {
            "AAPL": {"sector": "Technology", "_cached_at": "2099-01-01"}
        }
        monkeypatch.setattr(TickerMetadataService, "_is_cache_stale", classmethod(lambda cls, t: False))
        result = TickerMetadataService.get_sector("AAPL")
        assert result == "Technology"

    def test_get_industry_from_cache(self, monkeypatch):
        TickerMetadataService._cache = {
            "AAPL": {"industry": "Consumer Electronics", "_cached_at": "2099-01-01"}
        }
        monkeypatch.setattr(TickerMetadataService, "_is_cache_stale", classmethod(lambda cls, t: False))
        result = TickerMetadataService.get_industry("AAPL")
        assert result == "Consumer Electronics"

    def test_get_beta_from_cache(self, monkeypatch):
        TickerMetadataService._cache = {
            "AAPL": {"beta": 1.2, "_cached_at": "2099-01-01"}
        }
        monkeypatch.setattr(TickerMetadataService, "_is_cache_stale", classmethod(lambda cls, t: False))
        result = TickerMetadataService.get_beta("AAPL")
        assert result == 1.2

    def test_get_metadata_missing_returns_empty(self, monkeypatch):
        TickerMetadataService._cache = {}
        monkeypatch.setattr(
            TickerMetadataService, "_fetch_from_yfinance",
            classmethod(lambda cls, t: {}),
        )
        monkeypatch.setattr(TickerMetadataService, "_save_cache", classmethod(lambda cls: None))
        result = TickerMetadataService.get_metadata("NONEXISTENT")
        assert isinstance(result, dict)

    def test_clear_cache(self, tmp_path, monkeypatch):
        TickerMetadataService._cache = {"AAPL": {"sector": "Tech"}}
        monkeypatch.setattr(TickerMetadataService, "_CACHE_FILE", tmp_path / "meta.json")
        TickerMetadataService.clear_cache()
        assert TickerMetadataService._cache is None or len(TickerMetadataService._cache) == 0
