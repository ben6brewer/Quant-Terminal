"""Tests for risk_analytics.services.risk_analytics_service."""

import math

import numpy as np
import pandas as pd
import pytest

from app.ui.modules.risk_analytics.services.risk_analytics_service import (
    RiskAnalyticsService,
)


class TestTotalActiveRisk:
    def test_basic(self):
        rng = np.random.default_rng(42)
        port = pd.Series(rng.normal(0.0005, 0.015, 252))
        bench = pd.Series(rng.normal(0.0004, 0.012, 252))
        result = RiskAnalyticsService.calculate_total_active_risk(port, bench)
        assert isinstance(result, float)
        assert result > 0

    def test_identical_returns_zero(self):
        returns = pd.Series(np.random.default_rng(42).normal(0, 0.01, 252))
        result = RiskAnalyticsService.calculate_total_active_risk(returns, returns)
        assert abs(result) < 1e-10


class TestExPostBeta:
    def test_basic(self):
        rng = np.random.default_rng(42)
        bench = pd.Series(rng.normal(0, 0.01, 252))
        # Portfolio = 1.5 * benchmark + noise
        port = 1.5 * bench + pd.Series(rng.normal(0, 0.005, 252))
        result = RiskAnalyticsService.calculate_ex_post_beta(port, bench)
        assert abs(result - 1.5) < 0.2  # Approximate due to noise

    def test_self_beta_one(self):
        returns = pd.Series(np.random.default_rng(42).normal(0, 0.01, 252))
        result = RiskAnalyticsService.calculate_ex_post_beta(returns, returns)
        assert abs(result - 1.0) < 1e-10


class TestSummaryMetrics:
    def test_returns_dict(self):
        rng = np.random.default_rng(42)
        port = pd.Series(rng.normal(0.0005, 0.015, 252))
        bench = pd.Series(rng.normal(0.0004, 0.012, 252))
        result = RiskAnalyticsService.get_summary_metrics(
            port, bench,
            tickers=["AAPL", "MSFT"],
            weights={"AAPL": 0.5, "MSFT": 0.5},
        )
        assert isinstance(result, dict)
        assert "total_active_risk" in result
        assert "ex_post_beta" in result
