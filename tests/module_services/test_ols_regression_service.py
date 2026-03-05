"""Tests for analysis.services.ols_regression_service."""

import numpy as np
import pytest

from app.ui.modules.analysis.services.ols_regression_service import (
    OLSRegressionService,
)


class TestRunOLS:
    def test_basic_regression(self):
        """Simple y = 2x + 1 with noise."""
        rng = np.random.default_rng(42)
        n = 100
        x = rng.normal(0, 1, n)
        y = 2 * x + 1 + rng.normal(0, 0.1, n)

        X = np.column_stack([np.ones(n), x])
        result = OLSRegressionService._run_ols(X, y)

        assert "betas" in result
        assert "r_squared" in result
        # betas[0] = intercept (~1.0), betas[1] = slope (~2.0)
        assert abs(result["betas"][0] - 1.0) < 0.1
        assert abs(result["betas"][1] - 2.0) < 0.1
        assert result["r_squared"] > 0.95

    def test_perfect_fit(self):
        """Exact linear relationship: R²=1."""
        x = np.array([1, 2, 3, 4, 5], dtype=float)
        y = 3 * x + 2
        X = np.column_stack([np.ones(5), x])
        result = OLSRegressionService._run_ols(X, y)
        assert abs(result["r_squared"] - 1.0) < 1e-10

    def test_no_relationship(self):
        """Random data: R² should be low."""
        rng = np.random.default_rng(42)
        n = 200
        x = rng.normal(0, 1, n)
        y = rng.normal(0, 1, n)
        X = np.column_stack([np.ones(n), x])
        result = OLSRegressionService._run_ols(X, y)
        assert result["r_squared"] < 0.1

    def test_statistics_present(self):
        rng = np.random.default_rng(42)
        n = 100
        x = rng.normal(0, 1, n)
        y = x + rng.normal(0, 0.5, n)
        X = np.column_stack([np.ones(n), x])
        result = OLSRegressionService._run_ols(X, y)

        assert "adj_r_squared" in result
        assert "f_statistic" in result
        assert "durbin_watson" in result
        assert "t_stats" in result
        assert "p_values" in result
        assert "se_betas" in result
        assert len(result["t_stats"]) == 2  # intercept + slope
        assert len(result["p_values"]) == 2
        assert 0 <= result["durbin_watson"] <= 4


class TestGetAnnualizationFactor:
    def test_daily_stock(self):
        factor = OLSRegressionService._get_annualization_factor("AAPL", "daily")
        assert factor == 252

    def test_daily_crypto(self):
        factor = OLSRegressionService._get_annualization_factor("BTC-USD", "daily")
        assert factor == 365

    def test_weekly(self):
        factor = OLSRegressionService._get_annualization_factor("AAPL", "weekly")
        assert factor == 52

    def test_monthly(self):
        factor = OLSRegressionService._get_annualization_factor("AAPL", "monthly")
        assert factor == 12

    def test_yearly(self):
        factor = OLSRegressionService._get_annualization_factor("AAPL", "yearly")
        assert factor == 1
