"""OLS Regression Service - Stateless ordinary least squares regression."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    import numpy as np


@dataclass
class OLSRegressionResult:
    """Result container for OLS regression."""

    ticker_x: str
    ticker_y: str
    data_mode: str
    frequency: str
    n_observations: int

    # Scatter data
    x_values: "np.ndarray"
    y_values: "np.ndarray"
    x_label: str
    y_label: str

    # Coefficients (raw)
    alpha: float
    beta: float
    alpha_std_error: float
    beta_std_error: float
    alpha_t_stat: float
    beta_t_stat: float
    alpha_p_value: float
    beta_p_value: float

    # Annualized alpha
    annualized_alpha: float
    annualized_alpha_std_error: float
    annualized_alpha_ci_lower: float
    annualized_alpha_ci_upper: float
    annualization_factor: int

    # Confidence intervals (95%)
    alpha_ci_lower: float
    alpha_ci_upper: float
    beta_ci_lower: float
    beta_ci_upper: float

    # Goodness of fit
    r_squared: float
    adj_r_squared: float
    f_statistic: float
    f_p_value: float

    # Diagnostics
    durbin_watson: float
    residual_std_error: float

    # Regression line endpoints
    line_x: "np.ndarray"
    line_y: "np.ndarray"

    # Confidence band arrays (for chart)
    ci_band_x: "np.ndarray"
    ci_band_upper: "np.ndarray"
    ci_band_lower: "np.ndarray"


class OLSRegressionService:
    """Stateless OLS regression service.

    The private _run_ols() method is the reusable core for future
    multi-factor regression modules.
    """

    @staticmethod
    def _run_ols(X: "np.ndarray", y: "np.ndarray") -> dict:
        """Core OLS math on numpy arrays.

        Args:
            X: Design matrix with intercept column (n x k).
            y: Response vector (n,).

        Returns:
            Dict of raw regression results.
        """
        import numpy as np
        from scipy import stats as sp_stats

        n, k = X.shape

        # Normal equations with condition number check
        XtX = X.T @ X
        cond = np.linalg.cond(XtX)
        if cond > 1e10:
            XtX_inv = np.linalg.pinv(XtX)
        else:
            XtX_inv = np.linalg.inv(XtX)

        betas = XtX_inv @ (X.T @ y)

        # Fitted values and residuals
        fitted = X @ betas
        residuals = y - fitted

        # R-squared
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))

        # Adjusted R-squared (k includes intercept, so p = k - 1 predictors)
        if n > k:
            adj_r_squared = 1.0 - (1.0 - r_squared) * (n - 1) / (n - k)
        else:
            adj_r_squared = r_squared

        # Standard errors and t-statistics
        mse = ss_res / (n - k) if n > k else 1.0
        var_betas = np.diag(XtX_inv) * mse
        var_betas = np.maximum(var_betas, 1e-10)
        se_betas = np.sqrt(var_betas)
        t_stats = betas / se_betas

        # P-values (two-tailed t-distribution)
        df = max(n - k, 1)
        p_values = 2.0 * (1.0 - sp_stats.t.cdf(np.abs(t_stats), df=df))

        # F-statistic (overall significance)
        if k > 1 and n > k:
            ss_reg = ss_tot - ss_res
            df_reg = k - 1  # number of predictors (excluding intercept)
            df_resid = n - k
            ms_reg = ss_reg / df_reg if df_reg > 0 else 0.0
            ms_resid = mse
            f_stat = ms_reg / ms_resid if ms_resid > 0 else 0.0
            f_p_value = 1.0 - sp_stats.f.cdf(f_stat, df_reg, df_resid)
        else:
            f_stat = 0.0
            f_p_value = 1.0

        # Confidence intervals (95%)
        t_crit = sp_stats.t.ppf(0.975, df=df)
        ci_lower = betas - t_crit * se_betas
        ci_upper = betas + t_crit * se_betas

        # Durbin-Watson statistic
        diff_resid = np.diff(residuals)
        dw = np.sum(diff_resid ** 2) / ss_res if ss_res > 0 else 2.0

        # Residual standard error
        residual_std = np.sqrt(mse)

        return {
            "betas": betas,
            "se_betas": se_betas,
            "t_stats": t_stats,
            "p_values": p_values,
            "r_squared": r_squared,
            "adj_r_squared": adj_r_squared,
            "f_statistic": f_stat,
            "f_p_value": f_p_value,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "durbin_watson": dw,
            "residual_std": residual_std,
            "residuals": residuals,
            "fitted": fitted,
            "n": n,
            "k": k,
            "XtX_inv": XtX_inv,
            "mse": mse,
        }

    @staticmethod
    def _get_annualization_factor(ticker_x: str, frequency: str) -> int:
        """Get annualization factor based on ticker type and frequency."""
        from app.utils.market_hours import is_crypto_ticker

        if frequency == "daily":
            return 365 if is_crypto_ticker(ticker_x) else 252
        elif frequency == "weekly":
            return 52
        elif frequency == "monthly":
            return 12
        else:  # yearly
            return 1

    @staticmethod
    def compute_regression(
        ticker_x: str,
        ticker_y: str,
        data_mode: str = "simple_returns",
        frequency: str = "daily",
        lookback_days: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> OLSRegressionResult:
        """Run OLS regression of ticker_y on ticker_x.

        Args:
            ticker_x: Independent variable ticker.
            ticker_y: Dependent variable ticker.
            data_mode: One of "simple_returns", "log_returns", "price_levels".
            frequency: One of "daily", "weekly", "monthly", "yearly".
            lookback_days: Calendar days lookback (None = max).
            start_date: ISO date string for custom range start.
            end_date: ISO date string for custom range end.

        Returns:
            OLSRegressionResult with all statistics and chart data.
        """
        import numpy as np
        from scipy import stats as sp_stats
        from .frontier_calculation_service import FrontierCalculationService

        # Fetch aligned price data
        prices, daily_returns = FrontierCalculationService.compute_daily_returns(
            [ticker_x, ticker_y],
            lookback_days=lookback_days,
            start_date=start_date,
            end_date=end_date,
        )

        if daily_returns.empty or len(daily_returns) < 10:
            raise ValueError(
                f"Insufficient data: need at least 10 observations, "
                f"got {len(daily_returns)}"
            )

        # Ensure both tickers present
        for t in [ticker_x, ticker_y]:
            if t not in prices.columns:
                raise ValueError(f"No data available for {t}")

        # Resample prices if frequency is not daily
        freq_map = {"weekly": "W-FRI", "monthly": "ME", "yearly": "YE"}
        if frequency in freq_map:
            prices = prices.resample(freq_map[frequency]).last().dropna()
            if len(prices) < 10:
                raise ValueError(
                    f"Insufficient data after {frequency} resampling: "
                    f"{len(prices)} observations"
                )

        # Transform based on data mode
        freq_label = {
            "daily": "Daily", "weekly": "Weekly",
            "monthly": "Monthly", "yearly": "Yearly",
        }.get(frequency, "Daily")
        mode_labels = {
            "simple_returns": (f"{freq_label} Return", f"{freq_label} Return"),
            "log_returns": (f"{freq_label} Log Return", f"{freq_label} Log Return"),
            "price_levels": ("Price", "Price"),
        }

        if data_mode == "simple_returns":
            if frequency in freq_map:
                rets = prices.pct_change().dropna()
            else:
                rets = daily_returns
            if len(rets) < 10:
                raise ValueError("Insufficient data after computing returns")
            x_data = rets[ticker_x].values
            y_data = rets[ticker_y].values
        elif data_mode == "log_returns":
            log_rets = np.log(prices / prices.shift(1)).dropna()
            if len(log_rets) < 10:
                raise ValueError("Insufficient data after computing log returns")
            x_data = log_rets[ticker_x].values
            y_data = log_rets[ticker_y].values
        elif data_mode == "price_levels":
            x_data = prices[ticker_x].values
            y_data = prices[ticker_y].values
        else:
            raise ValueError(f"Unknown data_mode: {data_mode}")

        # Remove any NaN/inf
        mask = np.isfinite(x_data) & np.isfinite(y_data)
        x_data = x_data[mask]
        y_data = y_data[mask]

        if len(x_data) < 10:
            raise ValueError(
                f"Insufficient valid observations: {len(x_data)}"
            )

        # Build design matrix [1, x]
        X = np.column_stack([np.ones(len(x_data)), x_data])

        # Run core OLS
        result = OLSRegressionService._run_ols(X, y_data)

        alpha_val = float(result["betas"][0])
        beta_val = float(result["betas"][1])

        # Regression line (two endpoints spanning the x range)
        x_min, x_max = float(x_data.min()), float(x_data.max())
        line_x = np.array([x_min, x_max])
        line_y = alpha_val + beta_val * line_x

        # 95% confidence band for the mean response
        n_band = 100
        ci_band_x = np.linspace(x_min, x_max, n_band)
        x_mean = np.mean(x_data)

        # Variance of predicted mean: MSE * (1/n + (x - x_bar)^2 / sum((x_i - x_bar)^2))
        ss_xx = np.sum((x_data - x_mean) ** 2)
        df = max(result["n"] - result["k"], 1)
        t_crit = sp_stats.t.ppf(0.975, df=df)

        se_mean = np.sqrt(
            result["mse"] * (1.0 / result["n"] + (ci_band_x - x_mean) ** 2 / ss_xx)
        )
        ci_band_y_hat = alpha_val + beta_val * ci_band_x
        ci_band_upper = ci_band_y_hat + t_crit * se_mean
        ci_band_lower = ci_band_y_hat - t_crit * se_mean

        # Axis labels
        base_x, base_y = mode_labels.get(data_mode, ("Value", "Value"))
        x_label = f"{ticker_x} {base_x}"
        y_label = f"{ticker_y} {base_y}"

        # Annualize alpha
        ann_factor = OLSRegressionService._get_annualization_factor(
            ticker_x, frequency
        )
        raw_alpha_ci_lower = float(result["ci_lower"][0])
        raw_alpha_ci_upper = float(result["ci_upper"][0])
        raw_alpha_se = float(result["se_betas"][0])

        return OLSRegressionResult(
            ticker_x=ticker_x,
            ticker_y=ticker_y,
            data_mode=data_mode,
            frequency=frequency,
            n_observations=result["n"],
            x_values=x_data,
            y_values=y_data,
            x_label=x_label,
            y_label=y_label,
            alpha=alpha_val,
            beta=beta_val,
            alpha_std_error=raw_alpha_se,
            beta_std_error=float(result["se_betas"][1]),
            alpha_t_stat=float(result["t_stats"][0]),
            beta_t_stat=float(result["t_stats"][1]),
            alpha_p_value=float(result["p_values"][0]),
            beta_p_value=float(result["p_values"][1]),
            annualized_alpha=alpha_val * ann_factor,
            annualized_alpha_std_error=raw_alpha_se * ann_factor,
            annualized_alpha_ci_lower=raw_alpha_ci_lower * ann_factor,
            annualized_alpha_ci_upper=raw_alpha_ci_upper * ann_factor,
            annualization_factor=ann_factor,
            alpha_ci_lower=raw_alpha_ci_lower,
            alpha_ci_upper=raw_alpha_ci_upper,
            beta_ci_lower=float(result["ci_lower"][1]),
            beta_ci_upper=float(result["ci_upper"][1]),
            r_squared=result["r_squared"],
            adj_r_squared=result["adj_r_squared"],
            f_statistic=result["f_statistic"],
            f_p_value=result["f_p_value"],
            durbin_watson=result["durbin_watson"],
            residual_std_error=result["residual_std"],
            line_x=line_x,
            line_y=line_y,
            ci_band_x=ci_band_x,
            ci_band_upper=ci_band_upper,
            ci_band_lower=ci_band_lower,
        )
