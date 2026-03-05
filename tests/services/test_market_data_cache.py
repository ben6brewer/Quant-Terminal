"""Tests for app.services.market_data_cache.MarketDataCache."""

import pandas as pd
import pytest


class TestMarketDataCache:
    @pytest.fixture
    def cache(self, tmp_path, monkeypatch):
        """MarketDataCache using temp directory."""
        from app.services.market_data_cache import MarketDataCache

        monkeypatch.setattr(MarketDataCache, "_CACHE_DIR", tmp_path / "cache")
        return MarketDataCache()

    @pytest.fixture
    def sample_df(self):
        dates = pd.bdate_range("2024-01-02", periods=50)
        return pd.DataFrame(
            {"Open": range(50), "High": range(50), "Low": range(50), "Close": range(50), "Volume": range(50)},
            index=dates,
        )

    def test_save_and_load(self, cache, sample_df):
        cache.save_to_cache("AAPL", sample_df)
        loaded = cache.get_cached_data("AAPL")
        assert loaded is not None
        assert len(loaded) == 50
        assert isinstance(loaded.index, pd.DatetimeIndex)

    def test_has_cache(self, cache, sample_df):
        assert cache.has_cache("AAPL") is False
        cache.save_to_cache("AAPL", sample_df)
        assert cache.has_cache("AAPL") is True

    def test_no_cache_returns_none(self, cache):
        assert cache.get_cached_data("NONEXISTENT") is None

    def test_clear_single(self, cache, sample_df):
        cache.save_to_cache("AAPL", sample_df)
        cache.save_to_cache("MSFT", sample_df)
        cache.clear_cache("AAPL")
        assert cache.has_cache("AAPL") is False
        assert cache.has_cache("MSFT") is True

    def test_clear_all(self, cache, sample_df):
        cache.save_to_cache("AAPL", sample_df)
        cache.save_to_cache("MSFT", sample_df)
        cache.clear_cache()
        assert cache.has_cache("AAPL") is False
        assert cache.has_cache("MSFT") is False

    def test_get_last_cached_date(self, cache, sample_df):
        cache.save_to_cache("AAPL", sample_df)
        last = cache.get_last_cached_date("AAPL")
        assert last == sample_df.index.max()

    def test_get_last_cached_date_none(self, cache):
        assert cache.get_last_cached_date("NONEXISTENT") is None

    def test_save_empty_df(self, cache):
        """Saving empty df should be a no-op."""
        cache.save_to_cache("EMPTY", pd.DataFrame())
        assert cache.has_cache("EMPTY") is False

    def test_save_none_df(self, cache):
        cache.save_to_cache("NONE", None)
        assert cache.has_cache("NONE") is False

    def test_cache_info(self, cache, sample_df):
        info = cache.get_cache_info("AAPL")
        assert info["exists"] is False

        cache.save_to_cache("AAPL", sample_df)
        info = cache.get_cache_info("AAPL")
        assert info["exists"] is True
        assert info["num_records"] == 50

    def test_windows_reserved_names(self, cache, sample_df):
        """Ticker like 'CON' should still be cacheable."""
        cache.save_to_cache("CON", sample_df)
        loaded = cache.get_cached_data("CON")
        assert loaded is not None
        assert len(loaded) == 50

    def test_ticker_sanitization(self, cache, sample_df):
        """Tickers with / should be sanitized."""
        cache.save_to_cache("BRK/B", sample_df)
        loaded = cache.get_cached_data("BRK/B")
        assert loaded is not None
