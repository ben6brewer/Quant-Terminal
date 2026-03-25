"""Factor Regression Service — runs multi-factor regressions and computes attribution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .model_definitions import FactorModelSpec

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd


@dataclass
class FactorRegressionResult:
    """Result container for a factor model regression."""

    model_key: str
    model_name: str
    factor_names: list[str]
    frequency: str
    n_observations: int
    annualization_factor: int  # 252 / 52 / 12

    # Coefficients
    alpha: float  # Raw periodic alpha
    alpha_annualized: float  # alpha * ann_factor
    betas: dict[str, float] = field(default_factory=dict)  # factor_name -> beta
    std_errors: dict[str, float] = field(default_factory=dict)  # "Alpha" + factor names -> SE
    t_stats: dict[str, float] = field(default_factory=dict)
    p_values: dict[str, float] = field(default_factory=dict)
    ci_lower: dict[str, float] = field(default_factory=dict)  # 95% CI
    ci_upper: dict[str, float] = field(default_factory=dict)

    # Goodness of fit
    r_squared: float = 0.0
    adj_r_squared: float = 0.0
    f_statistic: float = 0.0
    f_p_value: float = 1.0
    durbin_watson: float = 2.0
    residual_std_error: float = 0.0

    # Attribution arrays (for charts)
    dates: "np.ndarray" = field(default_factory=lambda: __import__("numpy").array([]))
    asset_excess_returns: "np.ndarray" = field(default_factory=lambda: __import__("numpy").array([]))
    factor_contributions: dict[str, "np.ndarray"] = field(default_factory=dict)
    alpha_series: "np.ndarray" = field(default_factory=lambda: __import__("numpy").array([]))
    residuals: "np.ndarray" = field(default_factory=lambda: __import__("numpy").array([]))


class FactorRegressionService:
    """Stateless service — runs factor regressions using the OLS kernel."""

    # Minimum observations by frequency
    _MIN_OBS = {"daily": 126, "weekly": 60, "monthly": 30}

    @staticmethod
    def run_regression(
        asset_returns: "pd.Series",
        factor_returns: "pd.DataFrame",
        rf: "pd.Series",
        model_spec: FactorModelSpec,
        frequency: str,
    ) -> FactorRegressionResult:
        """Run a multi-factor regression and compute per-period attribution.

        Args:
            asset_returns: Raw asset returns (not excess). DatetimeIndex.
            factor_returns: Factor columns at the same frequency. DatetimeIndex.
            rf: Risk-free rate series at the same frequency. DatetimeIndex.
            model_spec: Which model to run.
            frequency: "daily" | "weekly" | "monthly".

        Returns:
            FactorRegressionResult with all statistics and attribution arrays.
        """
        import numpy as np
        import pandas as pd
        from app.ui.modules.analysis.services.ols_regression_service import (
            OLSRegressionService,
        )

        # Normalize monthly indices to month-start so asset (ME = month-end)
        # and factor data (1st-of-month from pandas_datareader) align correctly.
        if frequency == "monthly":
            asset_returns = asset_returns.copy()
            asset_returns.index = asset_returns.index.to_period("M").to_timestamp()
            factor_returns = factor_returns.copy()
            factor_returns.index = factor_returns.index.to_period("M").to_timestamp()
            rf = rf.copy()
            rf.index = rf.index.to_period("M").to_timestamp()

        # Align all series on common dates
        combined = pd.DataFrame({"asset": asset_returns})
        combined = combined.join(factor_returns, how="inner")
        combined = combined.join(rf.rename("RF"), how="inner")
        combined = combined.dropna()

        # Compute excess returns
        excess = combined["asset"] - combined["RF"]

        # Validate minimum observations
        min_obs = FactorRegressionService._MIN_OBS.get(frequency, 30)
        if len(excess) < min_obs:
            raise ValueError(
                f"Insufficient observations: {len(excess)} ({frequency}), "
                f"need at least {min_obs}"
            )

        # Build design matrix: [1 | factor_1 | ... | factor_k]
        factor_cols = list(model_spec.factors)
        F = combined[factor_cols].values
        y = excess.values
        ones = np.ones((len(y), 1))
        X = np.hstack([ones, F])

        # Run core OLS
        ols = OLSRegressionService._run_ols(X, y)

        betas_vec = ols["betas"]
        se_vec = ols["se_betas"]
        t_vec = ols["t_stats"]
        p_vec = ols["p_values"]
        ci_lo = ols["ci_lower"]
        ci_hi = ols["ci_upper"]

        alpha_raw = float(betas_vec[0])

        # Map results to named dicts
        names = ["Alpha"] + factor_cols
        betas_dict = {f: float(betas_vec[i + 1]) for i, f in enumerate(factor_cols)}
        se_dict = {n: float(se_vec[i]) for i, n in enumerate(names)}
        t_dict = {n: float(t_vec[i]) for i, n in enumerate(names)}
        p_dict = {n: float(p_vec[i]) for i, n in enumerate(names)}
        ci_lo_dict = {n: float(ci_lo[i]) for i, n in enumerate(names)}
        ci_hi_dict = {n: float(ci_hi[i]) for i, n in enumerate(names)}

        # Annualization
        ann_map = {"daily": 252, "weekly": 52, "monthly": 12}
        ann_factor = ann_map.get(frequency, 12)

        # Per-period factor contributions
        dates = combined.index.values
        factor_contribs = {}
        for i, f in enumerate(factor_cols):
            factor_contribs[f] = float(betas_vec[i + 1]) * combined[f].values

        alpha_series = np.full(len(y), alpha_raw)
        residuals = y - (alpha_raw + sum(factor_contribs[f] for f in factor_cols))

        return FactorRegressionResult(
            model_key=model_spec.key,
            model_name=model_spec.name,
            factor_names=factor_cols,
            frequency=frequency,
            n_observations=ols["n"],
            annualization_factor=ann_factor,
            alpha=alpha_raw,
            alpha_annualized=alpha_raw * ann_factor,
            betas=betas_dict,
            std_errors=se_dict,
            t_stats=t_dict,
            p_values=p_dict,
            ci_lower=ci_lo_dict,
            ci_upper=ci_hi_dict,
            r_squared=ols["r_squared"],
            adj_r_squared=ols["adj_r_squared"],
            f_statistic=ols["f_statistic"],
            f_p_value=ols["f_p_value"],
            durbin_watson=ols["durbin_watson"],
            residual_std_error=ols["residual_std"],
            dates=dates,
            asset_excess_returns=y,
            factor_contributions=factor_contribs,
            alpha_series=alpha_series,
            residuals=residuals,
        )
