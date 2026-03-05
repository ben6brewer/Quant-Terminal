"""Tests for app.services.market_data routing and classification."""

import numpy as np
import pandas as pd
import pytest

from app.services.market_data import TickerGroup, classify_tickers


class TestTickerGroup:
    def test_enum_values(self):
        assert TickerGroup.CACHE_CURRENT.value == "cache_current"
        assert TickerGroup.NEEDS_UPDATE.value == "needs_update"


class TestClassifyTickers:
    def test_empty_list(self):
        groups = classify_tickers([])
        assert len(groups[TickerGroup.CACHE_CURRENT]) == 0
        assert len(groups[TickerGroup.NEEDS_UPDATE]) == 0

    def test_unknown_tickers_need_update(self, monkeypatch):
        """Tickers with no cache should be classified as NEEDS_UPDATE."""
        from app.services import market_data

        # Clear memory cache
        with market_data._memory_cache_lock:
            market_data._memory_cache.clear()

        # Mock cache to return False for all
        monkeypatch.setattr(market_data._cache, "has_cache", lambda t: False)

        groups = classify_tickers(["AAPL", "MSFT"])
        assert len(groups[TickerGroup.NEEDS_UPDATE]) == 2
        assert len(groups[TickerGroup.CACHE_CURRENT]) == 0

    def test_normalizes_tickers(self, monkeypatch):
        """Tickers should be uppercased and stripped."""
        from app.services import market_data

        with market_data._memory_cache_lock:
            market_data._memory_cache.clear()

        monkeypatch.setattr(market_data._cache, "has_cache", lambda t: False)

        groups = classify_tickers(["  aapl  ", "msft"])
        tickers = [c.ticker for c in groups[TickerGroup.NEEDS_UPDATE]]
        assert "AAPL" in tickers
        assert "MSFT" in tickers


class TestResampleData:
    def test_daily_passthrough(self):
        from app.services.market_data import _resample_data

        dates = pd.bdate_range("2024-01-02", periods=100)
        df = pd.DataFrame(
            {"Open": range(100), "High": range(100), "Low": range(100), "Close": range(100)},
            index=dates,
        )
        result = _resample_data(df, "daily")
        assert len(result) == 100

    def test_weekly_resample(self):
        from app.services.market_data import _resample_data

        dates = pd.bdate_range("2024-01-02", periods=100)
        df = pd.DataFrame(
            {"Open": range(100), "High": range(100), "Low": range(100), "Close": range(100)},
            index=dates,
        )
        result = _resample_data(df, "weekly")
        assert len(result) < 100
        assert len(result) > 10

    def test_monthly_resample(self):
        from app.services.market_data import _resample_data

        dates = pd.bdate_range("2024-01-02", periods=252)
        df = pd.DataFrame(
            {"Open": range(252), "High": range(252), "Low": range(252), "Close": range(252)},
            index=dates,
        )
        result = _resample_data(df, "monthly")
        assert len(result) < 252

    def test_unknown_interval(self):
        from app.services.market_data import _resample_data

        dates = pd.bdate_range("2024-01-02", periods=10)
        df = pd.DataFrame(
            {"Open": range(10), "High": range(10), "Low": range(10), "Close": range(10)},
            index=dates,
        )
        result = _resample_data(df, "unknown")
        assert len(result) == 10  # Returns unchanged
