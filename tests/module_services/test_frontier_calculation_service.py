"""Tests for analysis.services.frontier_calculation_service."""

import numpy as np
import pandas as pd
import pytest

from app.ui.modules.analysis.services.frontier_calculation_service import (
    FrontierCalculationService,
)


class TestCorrelationMatrix:
    @staticmethod
    def _make_prices(sample_returns_df, tickers):
        """Build a synthetic prices DF from cumulative returns."""
        ret = sample_returns_df[tickers]
        prices = (1 + ret).cumprod() * 100
        return prices

    def test_returns_dict(self, monkeypatch, sample_returns_df):
        def mock_compute(tickers, lookback_days=None, **kw):
            prices = TestCorrelationMatrix._make_prices(sample_returns_df, tickers)
            return prices, sample_returns_df[tickers]

        monkeypatch.setattr(
            FrontierCalculationService, "compute_daily_returns",
            staticmethod(mock_compute),
        )
        result = FrontierCalculationService.calculate_correlation_matrix(
            ["AAPL", "MSFT", "GOOGL"]
        )
        assert "matrix" in result
        matrix = result["matrix"]
        assert matrix.shape == (3, 3)
        # Diagonal should be 1.0
        for i in range(3):
            assert abs(matrix.iloc[i, i] - 1.0) < 1e-10

    def test_symmetric(self, monkeypatch, sample_returns_df):
        def mock_compute(tickers, lookback_days=None, **kw):
            prices = TestCorrelationMatrix._make_prices(sample_returns_df, tickers)
            return prices, sample_returns_df[tickers]

        monkeypatch.setattr(
            FrontierCalculationService, "compute_daily_returns",
            staticmethod(mock_compute),
        )
        result = FrontierCalculationService.calculate_correlation_matrix(
            ["AAPL", "MSFT"]
        )
        matrix = result["matrix"]
        assert abs(matrix.iloc[0, 1] - matrix.iloc[1, 0]) < 1e-10


class TestCovarianceMatrix:
    def test_returns_dict(self, monkeypatch, sample_returns_df):
        def mock_compute(tickers, lookback_days=None, **kw):
            prices = (1 + sample_returns_df[tickers]).cumprod() * 100
            return prices, sample_returns_df[tickers]

        monkeypatch.setattr(
            FrontierCalculationService, "compute_daily_returns",
            staticmethod(mock_compute),
        )
        result = FrontierCalculationService.calculate_covariance_matrix(
            ["AAPL", "MSFT", "GOOGL"]
        )
        assert "matrix" in result
        matrix = result["matrix"]
        assert matrix.shape == (3, 3)
        # Diagonal (variances) should be positive
        for i in range(3):
            assert matrix.iloc[i, i] > 0


class TestResampleReturns:
    def test_weekly(self, sample_prices_df):
        result = FrontierCalculationService._resample_returns(sample_prices_df, "weekly")
        assert len(result) < len(sample_prices_df)

    def test_monthly(self, sample_prices_df):
        result = FrontierCalculationService._resample_returns(sample_prices_df, "monthly")
        assert len(result) < len(sample_prices_df)

    def test_daily_passthrough(self, sample_prices_df):
        result = FrontierCalculationService._resample_returns(sample_prices_df, "daily")
        assert len(result) == len(sample_prices_df) - 1  # pct_change drops first
