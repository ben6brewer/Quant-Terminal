"""Tests for app.services.ticker_returns_service.TickerReturnsService."""

import numpy as np
import pandas as pd
import pytest

from app.services.ticker_returns_service import TickerReturnsService


class TestGetTickerReturns:
    def test_returns_series(self, monkeypatch):
        """Should return a pandas Series of daily returns."""
        dates = pd.bdate_range("2024-01-02", periods=100)
        close = 100.0 * np.exp(np.cumsum(np.random.default_rng(42).normal(0, 0.01, 100)))
        mock_df = pd.DataFrame(
            {"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1000},
            index=dates,
        )
        monkeypatch.setattr(
            "app.services.market_data.fetch_price_history",
            lambda *a, **kw: mock_df,
        )
        result = TickerReturnsService.get_ticker_returns("AAPL")
        assert isinstance(result, pd.Series)
        assert len(result) == 99  # pct_change drops first

    def test_empty_data(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.market_data.fetch_price_history",
            lambda *a, **kw: pd.DataFrame(),
        )
        result = TickerReturnsService.get_ticker_returns("BADTICKER")
        assert result.empty
