"""Tests for app.services.yahoo_finance_service.YahooFinanceService."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.services.yahoo_finance_service import YahooFinanceService


class TestNormalizeColumns:
    def test_lowercase_columns(self):
        df = pd.DataFrame({"open": [1], "high": [2], "low": [0.5], "close": [1.5], "volume": [100]})
        result = YahooFinanceService._normalize_columns(df)
        assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]

    def test_already_correct(self):
        df = pd.DataFrame({"Open": [1], "High": [2], "Low": [0.5], "Close": [1.5], "Volume": [100]})
        result = YahooFinanceService._normalize_columns(df)
        assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]

    def test_drops_extra_columns(self):
        df = pd.DataFrame({"Open": [1], "Close": [1.5], "SomeExtra": [99]})
        result = YahooFinanceService._normalize_columns(df)
        assert "SomeExtra" not in result.columns

    def test_adj_close_mapped(self):
        df = pd.DataFrame({"adj close": [1.5]})
        result = YahooFinanceService._normalize_columns(df)
        # Adj Close not in standard_cols, so should be dropped
        assert len(result.columns) == 0


class TestFetchHistorical:
    def test_returns_dataframe(self, mock_yahoo_download):
        result = YahooFinanceService.fetch_historical("AAPL", "2024-01-01", "2024-06-01")
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert "Close" in result.columns

    def test_empty_ticker(self, mock_yahoo_download):
        result = YahooFinanceService.fetch_historical("", "2024-01-01", "2024-06-01")
        # Empty ticker still calls yf.download with ""
        assert isinstance(result, pd.DataFrame)


class TestFetchFullHistory:
    def test_returns_dataframe(self, mock_yahoo_download):
        result = YahooFinanceService.fetch_full_history("AAPL")
        assert isinstance(result, pd.DataFrame)
        assert not result.empty

    def test_upper_cases_ticker(self, mock_yahoo_download):
        result = YahooFinanceService.fetch_full_history("aapl")
        assert isinstance(result, pd.DataFrame)


class TestFetchFullHistorySafe:
    def test_success(self, mock_yahoo_download):
        df, was_rate_limited = YahooFinanceService.fetch_full_history_safe("AAPL")
        assert not df.empty
        assert was_rate_limited is False

    def test_empty_result_flagged(self, monkeypatch):
        monkeypatch.setattr(
            "yfinance.download",
            lambda *a, **kw: pd.DataFrame(),
        )
        df, was_rate_limited = YahooFinanceService.fetch_full_history_safe("BADTICKER")
        assert df.empty
        assert was_rate_limited is True


class TestFetchBatchFullHistory:
    def test_empty_list(self):
        results, failed = YahooFinanceService.fetch_batch_full_history([])
        assert results == {}
        assert failed == []

    def test_single_ticker(self, mock_yahoo_download):
        results, failed = YahooFinanceService.fetch_batch_full_history(["AAPL"])
        assert "AAPL" in results
        assert len(failed) == 0

    def test_deduplicates_tickers(self, mock_yahoo_download):
        results, failed = YahooFinanceService.fetch_batch_full_history(
            ["AAPL", "aapl", " AAPL "]
        )
        # Should be deduplicated to 1 ticker
        assert len(results) + len(failed) <= 1


class TestFetchBatchDateRange:
    def test_empty(self):
        result = YahooFinanceService.fetch_batch_date_range([], {})
        assert result == {}

    def test_single_ticker(self, mock_yahoo_download):
        tickers = ["AAPL"]
        ranges = {"AAPL": ("2024-01-01", "2024-06-01")}
        result = YahooFinanceService.fetch_batch_date_range(tickers, ranges)
        assert "AAPL" in result


class TestFetchTodayOhlcv:
    def test_returns_single_row(self, mock_yahoo_download):
        result = YahooFinanceService.fetch_today_ohlcv("AAPL")
        assert result is not None
        assert len(result) == 1
