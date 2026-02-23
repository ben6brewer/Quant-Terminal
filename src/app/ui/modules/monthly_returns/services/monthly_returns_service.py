"""Monthly Returns Service - Computes year×month returns grid."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class MonthlyReturnsService:
    """Stateless service for computing monthly returns grids."""

    MONTH_LABELS = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]

    @staticmethod
    def compute_monthly_grid(name: str, is_ticker: bool) -> "pd.DataFrame":
        """Compute a year×month returns grid for a ticker or portfolio.

        Args:
            name: Ticker symbol or portfolio name.
            is_ticker: True if name is a ticker, False if portfolio.

        Returns:
            DataFrame with years as rows (descending), month columns + YTD.
        """
        import pandas as pd

        if is_ticker:
            monthly = MonthlyReturnsService._get_ticker_monthly(name)
        else:
            monthly = MonthlyReturnsService._get_portfolio_monthly(name)

        if monthly is None or monthly.empty:
            return pd.DataFrame()

        return MonthlyReturnsService._build_grid(monthly)

    @staticmethod
    def _get_ticker_monthly(ticker: str) -> "pd.Series":
        """Get monthly returns for a single ticker."""
        import pandas as pd

        from app.services.market_data import fetch_price_history

        df = fetch_price_history(ticker, period="max", skip_live_bar=True)
        if df is None or df.empty or "Close" not in df.columns:
            return pd.Series(dtype=float)

        close = df["Close"]
        if not isinstance(close.index, pd.DatetimeIndex):
            close.index = pd.to_datetime(close.index)

        # Resample to month-end and compute percentage change
        monthly_close = close.resample("ME").last()
        monthly_returns = monthly_close.pct_change().dropna()
        return monthly_returns

    @staticmethod
    def _get_portfolio_monthly(name: str) -> "pd.Series":
        """Get monthly returns for a portfolio via geometric linking."""
        import pandas as pd

        from app.services.returns_data_service import ReturnsDataService

        daily = ReturnsDataService.get_time_varying_portfolio_returns(
            name, interval="daily"
        )
        if daily is None or daily.empty:
            return pd.Series(dtype=float)

        if not isinstance(daily.index, pd.DatetimeIndex):
            daily.index = pd.to_datetime(daily.index)

        # Geometric linking: (1+r).prod() - 1 per month
        monthly = daily.resample("ME").apply(lambda x: (1 + x).prod() - 1)
        return monthly

    @staticmethod
    def _build_grid(monthly_series: "pd.Series") -> "pd.DataFrame":
        """Build a year×month grid DataFrame from a monthly returns series.

        Returns:
            DataFrame with years as index (descending), columns
            ["Jan","Feb",...,"Dec","YTD"]. Values are decimal returns.
        """
        import pandas as pd
        import numpy as np

        years = sorted(monthly_series.index.year.unique())
        columns = MonthlyReturnsService.MONTH_LABELS + ["YTD"]

        data = {}
        for year in years:
            row = {}
            year_returns = monthly_series[monthly_series.index.year == year]

            for month_idx, label in enumerate(MonthlyReturnsService.MONTH_LABELS, 1):
                month_data = year_returns[year_returns.index.month == month_idx]
                if not month_data.empty:
                    row[label] = month_data.iloc[0]
                else:
                    row[label] = np.nan

            # YTD = compounded from all available months
            available = [
                row[m] for m in MonthlyReturnsService.MONTH_LABELS
                if not (isinstance(row[m], float) and np.isnan(row[m]))
            ]
            if available:
                ytd = 1.0
                for r in available:
                    ytd *= (1 + r)
                row["YTD"] = ytd - 1
            else:
                row["YTD"] = np.nan

            data[year] = row

        grid = pd.DataFrame.from_dict(data, orient="index", columns=columns)
        # Sort descending (newest year first)
        grid = grid.sort_index(ascending=False)
        return grid
