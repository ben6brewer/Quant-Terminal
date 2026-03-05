"""Tests for app.services.ticker_name_cache.TickerNameCache."""

import json

import pytest

from app.services.ticker_name_cache import TickerNameCache


class TestTickerNameCache:
    @pytest.fixture(autouse=True)
    def reset_cache(self, tmp_path, monkeypatch):
        TickerNameCache._cache = None
        monkeypatch.setattr(TickerNameCache, "_CACHE_FILE", tmp_path / "names.json")
        yield
        TickerNameCache._cache = None

    def test_set_and_get(self):
        TickerNameCache.set_name("AAPL", "Apple Inc.")
        assert TickerNameCache.get_name("AAPL") == "Apple Inc."

    def test_get_missing(self):
        assert TickerNameCache.get_name("NONEXISTENT") is None

    def test_update_names(self):
        TickerNameCache.update_names({"AAPL": "Apple", "MSFT": "Microsoft"})
        assert TickerNameCache.get_name("AAPL") == "Apple"
        assert TickerNameCache.get_name("MSFT") == "Microsoft"

    def test_get_names(self):
        TickerNameCache.update_names({"AAPL": "Apple", "MSFT": "Microsoft"})
        result = TickerNameCache.get_names(["AAPL", "GOOGL"])
        assert result["AAPL"] == "Apple"
        assert result["GOOGL"] is None

    def test_get_missing_tickers(self):
        TickerNameCache.update_names({"AAPL": "Apple"})
        missing = TickerNameCache.get_missing_tickers(["AAPL", "MSFT", "GOOGL"])
        assert "MSFT" in missing
        assert "GOOGL" in missing
        assert "AAPL" not in missing

    def test_load_names(self):
        TickerNameCache.update_names({"AAPL": "Apple", "MSFT": "Microsoft"})
        names = TickerNameCache.load_names()
        assert isinstance(names, dict)
        assert "AAPL" in names

    def test_clear_cache(self):
        TickerNameCache.update_names({"AAPL": "Apple"})
        TickerNameCache.clear_cache()
        assert TickerNameCache.get_name("AAPL") is None
