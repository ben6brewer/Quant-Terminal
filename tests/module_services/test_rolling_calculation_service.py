"""Tests for analysis.services.rolling_calculation_service."""

import numpy as np
import pandas as pd
import pytest

from app.ui.modules.analysis.services.rolling_calculation_service import (
    RollingCalculationService,
)


def _mock_compute(sample_returns_df):
    """Build a mock compute_daily_returns that returns prices + returns."""
    def _inner(tickers, lookback_days=None, **kw):
        ret = sample_returns_df[tickers]
        prices = (1 + ret).cumprod() * 100
        return prices, ret
    return _inner


class TestRollingCorrelation:
    def test_returns_arrays(self, monkeypatch, sample_returns_df):
        from app.ui.modules.analysis.services import frontier_calculation_service as fcs

        monkeypatch.setattr(
            fcs.FrontierCalculationService,
            "compute_daily_returns",
            staticmethod(_mock_compute(sample_returns_df)),
        )
        dates, values = RollingCalculationService.compute_rolling_correlation(
            "AAPL", "MSFT", window=63
        )
        assert isinstance(dates, np.ndarray)
        assert isinstance(values, np.ndarray)
        assert len(dates) == len(values)
        assert len(values) > 0

    def test_values_in_range(self, monkeypatch, sample_returns_df):
        from app.ui.modules.analysis.services import frontier_calculation_service as fcs

        monkeypatch.setattr(
            fcs.FrontierCalculationService,
            "compute_daily_returns",
            staticmethod(_mock_compute(sample_returns_df)),
        )
        _, values = RollingCalculationService.compute_rolling_correlation(
            "AAPL", "MSFT", window=63
        )
        valid = values[~np.isnan(values)]
        assert np.all(valid >= -1.0)
        assert np.all(valid <= 1.0)


class TestRollingCovariance:
    def test_returns_arrays(self, monkeypatch, sample_returns_df):
        from app.ui.modules.analysis.services import frontier_calculation_service as fcs

        monkeypatch.setattr(
            fcs.FrontierCalculationService,
            "compute_daily_returns",
            staticmethod(_mock_compute(sample_returns_df)),
        )
        dates, values = RollingCalculationService.compute_rolling_covariance(
            "AAPL", "MSFT", window=63
        )
        assert isinstance(dates, np.ndarray)
        assert isinstance(values, np.ndarray)
        assert len(dates) > 0
