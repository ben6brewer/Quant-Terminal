"""Tests for app.services.returns_data_service.ReturnsDataService."""

import numpy as np
import pandas as pd
import pytest

from app.services.returns_data_service import ReturnsDataService


class TestFilterDateRange:
    def test_no_filter(self):
        dates = pd.bdate_range("2024-01-02", periods=50)
        df = pd.DataFrame({"A": range(50)}, index=dates)
        result = ReturnsDataService._filter_date_range(df, None, None)
        assert len(result) == 50

    def test_start_filter(self):
        dates = pd.bdate_range("2024-01-02", periods=50)
        df = pd.DataFrame({"A": range(50)}, index=dates)
        result = ReturnsDataService._filter_date_range(df, "2024-02-01", None)
        assert result.index.min() >= pd.Timestamp("2024-02-01")

    def test_end_filter(self):
        dates = pd.bdate_range("2024-01-02", periods=50)
        df = pd.DataFrame({"A": range(50)}, index=dates)
        result = ReturnsDataService._filter_date_range(df, None, "2024-02-01")
        assert result.index.max() <= pd.Timestamp("2024-02-01")

    def test_both_filters(self):
        dates = pd.bdate_range("2024-01-02", periods=100)
        df = pd.DataFrame({"A": range(100)}, index=dates)
        result = ReturnsDataService._filter_date_range(df, "2024-02-01", "2024-03-01")
        assert result.index.min() >= pd.Timestamp("2024-02-01")
        assert result.index.max() <= pd.Timestamp("2024-03-01")

    def test_empty_df(self):
        df = pd.DataFrame()
        result = ReturnsDataService._filter_date_range(df, "2024-01-01", "2024-12-31")
        assert result.empty


class TestResampleReturns:
    def test_weekly(self):
        dates = pd.bdate_range("2024-01-02", periods=100)
        returns = pd.Series(np.random.default_rng(42).normal(0, 0.01, 100), index=dates)
        result = ReturnsDataService._resample_returns(returns, "weekly")
        assert len(result) < 100

    def test_monthly(self):
        dates = pd.bdate_range("2024-01-02", periods=252)
        returns = pd.Series(np.random.default_rng(42).normal(0, 0.01, 252), index=dates)
        result = ReturnsDataService._resample_returns(returns, "monthly")
        assert len(result) < 252

    def test_daily_passthrough(self):
        returns = pd.Series([0.01, 0.02])
        result = ReturnsDataService._resample_returns(returns, "daily")
        assert len(result) == 2

    def test_empty(self):
        result = ReturnsDataService._resample_returns(pd.Series(dtype=float), "weekly")
        assert result.empty


class TestDistributionStatistics:
    def test_basic(self):
        rng = np.random.default_rng(42)
        returns = pd.Series(rng.normal(0.001, 0.02, 252))
        stats = ReturnsDataService.get_distribution_statistics(returns)
        assert stats["count"] == 252
        assert isinstance(stats["mean"], float)
        assert isinstance(stats["std"], float)

    def test_empty(self):
        stats = ReturnsDataService.get_distribution_statistics(pd.Series(dtype=float))
        assert stats["count"] == 0

    def test_none(self):
        stats = ReturnsDataService.get_distribution_statistics(None)
        assert stats["count"] == 0


class TestInvalidateCache:
    def test_invalidate_clears_memory(self):
        ReturnsDataService._memory_cache["test_portfolio"] = "dummy"
        ReturnsDataService.invalidate_cache("test_portfolio")
        assert "test_portfolio" not in ReturnsDataService._memory_cache

    def test_invalidate_all(self):
        ReturnsDataService._memory_cache["p1"] = "a"
        ReturnsDataService._memory_cache["p2"] = "b"
        ReturnsDataService.invalidate_all_caches()
        assert len(ReturnsDataService._memory_cache) == 0
