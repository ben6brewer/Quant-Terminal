"""Tests for monthly_returns.services.monthly_returns_service."""

import numpy as np
import pandas as pd
import pytest

from app.ui.modules.monthly_returns.services.monthly_returns_service import (
    MonthlyReturnsService,
)


class TestBuildGrid:
    def test_basic_grid(self):
        """Test grid building from monthly returns series."""
        dates = pd.date_range("2022-01-31", periods=24, freq="ME")
        returns = pd.Series(np.random.default_rng(42).normal(0.01, 0.05, 24), index=dates)
        grid = MonthlyReturnsService._build_grid(returns)

        assert isinstance(grid, pd.DataFrame)
        assert len(grid) > 0
        # Should have 13 columns: Jan-Dec + YTD
        assert len(grid.columns) == 13

    def test_ytd_column(self):
        """YTD should be compound of all months in the year."""
        dates = pd.date_range("2023-01-31", periods=12, freq="ME")
        # Constant 1% monthly return
        returns = pd.Series([0.01] * 12, index=dates)
        grid = MonthlyReturnsService._build_grid(returns)

        ytd = grid.loc[2023, "YTD"]
        # Compound: (1.01)^12 - 1 ≈ 12.68%
        expected = (1.01 ** 12) - 1
        assert abs(ytd - expected) < 0.001

    def test_years_descending(self):
        """Years should be sorted descending (most recent first)."""
        dates = pd.date_range("2020-01-31", periods=48, freq="ME")
        returns = pd.Series(np.random.default_rng(42).normal(0, 0.03, 48), index=dates)
        grid = MonthlyReturnsService._build_grid(returns)
        years = list(grid.index)
        assert years == sorted(years, reverse=True)


class TestMonthLabels:
    def test_defined(self):
        assert hasattr(MonthlyReturnsService, "MONTH_LABELS")
        assert len(MonthlyReturnsService.MONTH_LABELS) == 12
        assert MonthlyReturnsService.MONTH_LABELS[0] == "Jan"
        assert MonthlyReturnsService.MONTH_LABELS[11] == "Dec"
