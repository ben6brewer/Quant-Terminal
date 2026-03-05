"""Tests for monte_carlo.services.monte_carlo_service."""

import numpy as np
import pandas as pd
import pytest

from app.ui.modules.monte_carlo.services.monte_carlo_service import (
    MonteCarloService,
    SimulationResult,
)


class TestSimulateHistoricalBootstrap:
    @pytest.fixture
    def returns(self):
        rng = np.random.default_rng(42)
        return pd.Series(rng.normal(0.0003, 0.015, 504), index=pd.bdate_range("2023-01-02", periods=504))

    def test_returns_simulation_result(self, returns):
        result = MonteCarloService.simulate_historical_bootstrap(
            returns, n_simulations=100, n_periods=63, seed=42
        )
        assert isinstance(result, SimulationResult)

    def test_shape(self, returns):
        result = MonteCarloService.simulate_historical_bootstrap(
            returns, n_simulations=50, n_periods=63, seed=42
        )
        assert result.paths.shape == (50, 64)  # n_simulations × (n_periods + 1)

    def test_starts_at_initial_value(self, returns):
        result = MonteCarloService.simulate_historical_bootstrap(
            returns, n_simulations=50, n_periods=63, initial_value=1000, seed=42
        )
        assert np.allclose(result.paths[:, 0], 1000.0)

    def test_terminal_values(self, returns):
        result = MonteCarloService.simulate_historical_bootstrap(
            returns, n_simulations=100, n_periods=252, seed=42
        )
        assert len(result.terminal_values) == 100
        assert all(v > 0 for v in result.terminal_values)

    def test_reproducible_with_seed(self, returns):
        r1 = MonteCarloService.simulate_historical_bootstrap(returns, n_simulations=50, seed=42)
        r2 = MonteCarloService.simulate_historical_bootstrap(returns, n_simulations=50, seed=42)
        assert np.allclose(r1.paths, r2.paths)


class TestSimulateParametric:
    def test_basic(self):
        result = MonteCarloService.simulate_parametric(
            mean=0.0003, std=0.015, n_simulations=100, n_periods=252, seed=42
        )
        assert isinstance(result, SimulationResult)
        assert result.paths.shape == (100, 253)

    def test_higher_vol_wider_spread(self):
        r_low = MonteCarloService.simulate_parametric(mean=0, std=0.01, n_simulations=500, seed=42)
        r_high = MonteCarloService.simulate_parametric(mean=0, std=0.03, n_simulations=500, seed=42)
        spread_low = np.std(r_low.terminal_values)
        spread_high = np.std(r_high.terminal_values)
        assert spread_high > spread_low


class TestVarCvar:
    def test_basic(self):
        terminal = np.random.default_rng(42).normal(110, 20, 1000)
        result = MonteCarloService.calculate_var_cvar(terminal, initial_value=100)
        assert isinstance(result, dict)
        # Keys may be strings or floats
        key_95 = "0.95" if "0.95" in result else 0.95
        assert key_95 in result
        assert "var_pct" in result[key_95]
        assert "cvar_pct" in result[key_95]

    def test_cvar_worse_than_var(self):
        terminal = np.random.default_rng(42).normal(110, 20, 1000)
        result = MonteCarloService.calculate_var_cvar(terminal, initial_value=100)
        key_95 = "0.95" if "0.95" in result else 0.95
        assert result[key_95]["cvar_pct"] <= result[key_95]["var_pct"]


class TestProbabilityMetrics:
    def test_basic(self):
        # Most are gains
        terminal = np.random.default_rng(42).normal(120, 15, 1000)
        result = MonteCarloService.calculate_probability_metrics(terminal, initial_value=100)
        assert "prob_positive" in result
        assert 0 <= result["prob_positive"] <= 100


class TestSimulationResult:
    def test_mean_path(self):
        paths = np.array([[100, 105, 110], [100, 95, 105]])
        result = SimulationResult(
            paths=paths,
            terminal_values=paths[:, -1],
            dates=None,
            percentiles={},
        )
        mean = result.mean_path
        assert len(mean) == 3
        assert mean[0] == 100
        assert mean[2] == 107.5

    def test_median_terminal(self):
        paths = np.array([[100, 110], [100, 90], [100, 100]])
        result = SimulationResult(
            paths=paths,
            terminal_values=paths[:, -1],
            dates=None,
            percentiles={},
        )
        assert result.median_terminal == 100.0
