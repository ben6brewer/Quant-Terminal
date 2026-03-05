"""Tests for app.services.statistics_service.StatisticsService."""

import math

import numpy as np
import pandas as pd
import pytest

from app.services.statistics_service import StatisticsService


class TestTotalReturn:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_total_return(sample_returns_series)
        assert isinstance(result, float)
        assert not math.isnan(result)

    def test_empty(self):
        assert math.isnan(StatisticsService.get_total_return(pd.Series(dtype=float)))

    def test_none(self):
        assert math.isnan(StatisticsService.get_total_return(None))

    def test_all_nan(self):
        s = pd.Series([float("nan")] * 10)
        assert math.isnan(StatisticsService.get_total_return(s))

    def test_known_values(self):
        # 10% + 10% compounded = 21%
        s = pd.Series([0.10, 0.10])
        result = StatisticsService.get_total_return(s)
        assert abs(result - 0.21) < 1e-10


class TestAnnualizedReturn:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_annualized_return(sample_returns_series)
        assert isinstance(result, float)
        assert not math.isnan(result)

    def test_empty(self):
        assert math.isnan(StatisticsService.get_annualized_return(pd.Series(dtype=float)))

    def test_positive_returns(self):
        # Constant daily return of 0.04% ≈ ~10% annualized
        s = pd.Series([0.0004] * 252)
        result = StatisticsService.get_annualized_return(s)
        assert abs(result - 0.1008) < 0.01


class TestMaxMinReturn:
    def test_max(self, sample_returns_series):
        result = StatisticsService.get_max_return(sample_returns_series)
        assert result == sample_returns_series.dropna().max()

    def test_min(self, sample_returns_series):
        result = StatisticsService.get_min_return(sample_returns_series)
        assert result == sample_returns_series.dropna().min()

    def test_empty_max(self):
        assert math.isnan(StatisticsService.get_max_return(pd.Series(dtype=float)))

    def test_empty_min(self):
        assert math.isnan(StatisticsService.get_min_return(pd.Series(dtype=float)))


class TestMeanExcessReturn:
    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.get_mean_excess_return(
            sample_returns_series, sample_benchmark_returns
        )
        assert isinstance(result, float)
        assert not math.isnan(result)

    def test_none_inputs(self):
        assert math.isnan(StatisticsService.get_mean_excess_return(None, None))


class TestAnnualizedVolatility:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_annualized_volatility(sample_returns_series)
        assert result > 0
        # Typical stock vol is 15-40%
        assert 0.05 < result < 1.0

    def test_empty(self):
        assert math.isnan(
            StatisticsService.get_annualized_volatility(pd.Series(dtype=float))
        )

    def test_single_value(self):
        assert math.isnan(StatisticsService.get_annualized_volatility(pd.Series([0.01])))


class TestDownsideRisk:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_downside_risk(sample_returns_series)
        assert result >= 0

    def test_all_positive(self):
        s = pd.Series([0.01, 0.02, 0.03, 0.04])
        result = StatisticsService.get_downside_risk(s, target=0.0)
        assert result == 0.0


class TestSkewnessKurtosis:
    def test_skewness(self, sample_returns_series):
        result = StatisticsService.get_skewness(sample_returns_series)
        assert isinstance(result, float)
        assert -3 < result < 3  # Reasonable range

    def test_kurtosis(self, sample_returns_series):
        result = StatisticsService.get_kurtosis(sample_returns_series)
        assert isinstance(result, float)

    def test_too_few_for_skew(self):
        assert math.isnan(StatisticsService.get_skewness(pd.Series([0.01, 0.02])))

    def test_too_few_for_kurt(self):
        assert math.isnan(StatisticsService.get_kurtosis(pd.Series([0.01, 0.02, 0.03])))


class TestVaR:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_var(sample_returns_series, confidence=0.95)
        assert result < 0  # VaR is negative (loss)

    def test_higher_confidence_more_extreme(self, sample_returns_series):
        var_95 = StatisticsService.get_var(sample_returns_series, 0.95)
        var_99 = StatisticsService.get_var(sample_returns_series, 0.99)
        assert var_99 < var_95  # 99% VaR is more extreme

    def test_insufficient_data(self):
        s = pd.Series([0.01] * 10)
        assert math.isnan(StatisticsService.get_var(s))


class TestCVaR:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_cvar(sample_returns_series, confidence=0.95)
        assert result < 0

    def test_cvar_worse_than_var(self, sample_returns_series):
        var = StatisticsService.get_var(sample_returns_series, 0.95)
        cvar = StatisticsService.get_cvar(sample_returns_series, 0.95)
        assert cvar <= var  # CVaR is always worse than VaR


class TestMaxDrawdown:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_max_drawdown(sample_returns_series)
        assert result < 0  # Drawdowns are negative
        assert result >= -1.0  # Can't lose more than 100%

    def test_all_positive_still_has_drawdown(self):
        # Even with overall positive, there can be small drawdowns
        rng = np.random.default_rng(42)
        s = pd.Series(rng.normal(0.001, 0.01, 252))
        result = StatisticsService.get_max_drawdown(s)
        assert result <= 0


class TestSharpeRatio:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_sharpe_ratio(sample_returns_series)
        assert isinstance(result, float)
        assert not math.isnan(result)

    def test_with_risk_free(self, sample_returns_series):
        result = StatisticsService.get_sharpe_ratio(sample_returns_series, risk_free_rate=0.05)
        assert isinstance(result, float)

    def test_empty(self):
        assert math.isnan(StatisticsService.get_sharpe_ratio(pd.Series(dtype=float)))

    def test_zero_vol(self):
        # Constant returns = near-zero volatility → extremely large or NaN Sharpe
        s = pd.Series([0.001] * 100)
        result = StatisticsService.get_sharpe_ratio(s)
        assert math.isnan(result) or abs(result) > 1e10


class TestSortinoRatio:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_sortino_ratio(sample_returns_series)
        assert isinstance(result, float)

    def test_empty(self):
        assert math.isnan(StatisticsService.get_sortino_ratio(pd.Series(dtype=float)))


class TestBeta:
    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.get_beta(sample_returns_series, sample_benchmark_returns)
        assert isinstance(result, float)
        assert not math.isnan(result)

    def test_self_beta_is_one(self):
        """Beta of a series with itself should be 1.0."""
        s = pd.Series(np.random.default_rng(42).normal(0, 0.01, 252))
        result = StatisticsService.get_beta(s, s)
        assert abs(result - 1.0) < 1e-10

    def test_none_inputs(self):
        assert math.isnan(StatisticsService.get_beta(None, None))

    def test_zero_benchmark_variance(self):
        """Constant benchmark should give NaN beta."""
        port = pd.Series([0.01, 0.02, 0.03])
        bench = pd.Series([0.01, 0.01, 0.01])
        assert math.isnan(StatisticsService.get_beta(port, bench))


class TestAlpha:
    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.get_alpha(
            sample_returns_series, sample_benchmark_returns
        )
        assert isinstance(result, float)

    def test_with_risk_free(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.get_alpha(
            sample_returns_series, sample_benchmark_returns, risk_free_rate=0.05
        )
        assert isinstance(result, float)


class TestTrackingError:
    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.get_tracking_error(
            sample_returns_series, sample_benchmark_returns
        )
        assert result > 0

    def test_self_tracking_zero(self):
        """Tracking error with itself should be ~0."""
        s = pd.Series(np.random.default_rng(42).normal(0, 0.01, 252))
        result = StatisticsService.get_tracking_error(s, s)
        assert abs(result) < 1e-10


class TestInformationRatio:
    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.get_information_ratio(
            sample_returns_series, sample_benchmark_returns
        )
        assert isinstance(result, float)


class TestCorrelation:
    def test_self_correlation(self):
        s = pd.Series(np.random.default_rng(42).normal(0, 0.01, 252))
        result = StatisticsService.get_correlation(s, s)
        assert abs(result - 1.0) < 1e-10

    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.get_correlation(
            sample_returns_series, sample_benchmark_returns
        )
        assert -1 <= result <= 1


class TestRSquared:
    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.get_r_squared(
            sample_returns_series, sample_benchmark_returns
        )
        assert 0 <= result <= 1


class TestCaptureRatio:
    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        up, down = StatisticsService.get_capture_ratio(
            sample_returns_series, sample_benchmark_returns
        )
        assert isinstance(up, float)
        assert isinstance(down, float)

    def test_none_inputs(self):
        up, down = StatisticsService.get_capture_ratio(None, None)
        assert math.isnan(up)
        assert math.isnan(down)

    def test_insufficient_data(self):
        p = pd.Series([0.01, 0.02])
        b = pd.Series([0.01, 0.02])
        up, down = StatisticsService.get_capture_ratio(p, b)
        assert math.isnan(up)


class TestTreynorRatio:
    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.get_treynor_ratio(
            sample_returns_series, sample_benchmark_returns
        )
        assert isinstance(result, float)


class TestDistributionStatistics:
    def test_basic(self, sample_returns_series):
        result = StatisticsService.get_distribution_statistics(sample_returns_series)
        assert "mean" in result
        assert "std" in result
        assert "skew" in result
        assert "kurtosis" in result
        assert "min" in result
        assert "max" in result
        assert result["count"] == len(sample_returns_series)

    def test_empty(self):
        result = StatisticsService.get_distribution_statistics(pd.Series(dtype=float))
        assert result["count"] == 0
        assert math.isnan(result["mean"])

    def test_none(self):
        result = StatisticsService.get_distribution_statistics(None)
        assert result["count"] == 0


class TestAlignReturns:
    def test_basic(self, sample_returns_series, sample_benchmark_returns):
        result = StatisticsService.align_returns(
            sample_returns_series, sample_benchmark_returns
        )
        assert "portfolio" in result.columns
        assert "benchmark" in result.columns
        assert len(result) > 0

    def test_none_inputs(self):
        result = StatisticsService.align_returns(None, None)
        assert result.empty
