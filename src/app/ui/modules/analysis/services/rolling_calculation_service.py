"""Rolling Calculation Service - Rolling correlation and covariance computations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    import numpy as np


class RollingCalculationService:
    """Stateless service for rolling correlation and covariance calculations.

    Reuses FrontierCalculationService.compute_daily_returns() for data fetching.
    """

    @staticmethod
    def compute_rolling_correlation(
        ticker1: str,
        ticker2: str,
        window: int,
        lookback_days: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple["np.ndarray", "np.ndarray"]:
        """Compute rolling Pearson correlation between two tickers.

        Returns (dates_array, values_array) as numpy arrays.
        """
        import numpy as np
        from .frontier_calculation_service import FrontierCalculationService

        _, daily_returns = FrontierCalculationService.compute_daily_returns(
            [ticker1, ticker2], lookback_days,
            start_date=start_date, end_date=end_date,
        )

        if daily_returns.empty or len(daily_returns.columns) < 2:
            raise ValueError("Insufficient data for the selected tickers")

        if len(daily_returns) < window:
            raise ValueError(
                f"Not enough data ({len(daily_returns)} days) for "
                f"rolling window of {window} days"
            )

        col1, col2 = daily_returns.columns[0], daily_returns.columns[1]
        rolling_corr = daily_returns[col1].rolling(window).corr(daily_returns[col2]).dropna()

        dates = np.array(rolling_corr.index.values, dtype="datetime64[ns]")
        values = rolling_corr.values.astype(np.float64)

        return dates, values

    @staticmethod
    def compute_rolling_covariance(
        ticker1: str,
        ticker2: str,
        window: int,
        lookback_days: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple["np.ndarray", "np.ndarray"]:
        """Compute rolling annualized covariance between two tickers.

        Returns (dates_array, values_array) as numpy arrays.
        """
        import numpy as np
        from .frontier_calculation_service import FrontierCalculationService

        _, daily_returns = FrontierCalculationService.compute_daily_returns(
            [ticker1, ticker2], lookback_days,
            start_date=start_date, end_date=end_date,
        )

        if daily_returns.empty or len(daily_returns.columns) < 2:
            raise ValueError("Insufficient data for the selected tickers")

        if len(daily_returns) < window:
            raise ValueError(
                f"Not enough data ({len(daily_returns)} days) for "
                f"rolling window of {window} days"
            )

        col1, col2 = daily_returns.columns[0], daily_returns.columns[1]
        rolling_cov = daily_returns[col1].rolling(window).cov(daily_returns[col2]).dropna() * 252

        dates = np.array(rolling_cov.index.values, dtype="datetime64[ns]")
        values = rolling_cov.values.astype(np.float64)

        return dates, values
