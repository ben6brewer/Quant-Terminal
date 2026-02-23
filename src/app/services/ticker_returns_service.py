"""Ticker Returns Service - Single-ticker return analysis methods."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import pandas as pd


class TickerReturnsService:
    """Return analysis for individual tickers (not portfolios)."""

    @classmethod
    def get_ticker_returns(
        cls,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: str = "daily",
    ) -> "pd.Series":
        """
        Get returns for a single ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            interval: Return interval - "daily", "weekly", "monthly", "yearly"

        Returns:
            Series of returns (as decimals, e.g., 0.05 = 5%)
        """
        import pandas as pd
        from app.services.market_data import fetch_price_history

        # skip_live_bar=True - returns calculations use daily closes, not intraday
        df = fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=True)
        if df.empty:
            return pd.Series(dtype=float)

        # Calculate daily returns
        returns = df["Close"].pct_change().dropna()
        returns.name = ticker

        # Filter date range
        if start_date or end_date:
            from app.services.returns_data_service import ReturnsDataService
            returns_df = returns.to_frame()
            returns_df = ReturnsDataService._filter_date_range(returns_df, start_date, end_date)
            returns = returns_df[ticker] if ticker in returns_df.columns else returns_df.iloc[:, 0]

        # Resample if needed
        if interval.lower() != "daily":
            from app.services.returns_data_service import ReturnsDataService
            returns = ReturnsDataService._resample_returns(returns, interval)

        return returns

    @classmethod
    def get_ticker_volatility(
        cls,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.Series":
        """
        Calculate annualized volatility series for a single ticker.

        Returns a series of rolling 21-day volatility values (annualized).
        """
        import numpy as np
        import pandas as pd

        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty or len(returns) < 21:
            return pd.Series(dtype=float)

        # Calculate rolling 21-day volatility, annualized
        rolling_vol = returns.rolling(window=21).std() * np.sqrt(252)

        return rolling_vol.dropna()

    @classmethod
    def get_ticker_rolling_volatility(
        cls,
        ticker: str,
        window_days: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.Series":
        """
        Calculate rolling volatility with specified window for a single ticker.
        """
        import numpy as np
        import pandas as pd

        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty or len(returns) < window_days:
            return pd.Series(dtype=float)

        # Calculate rolling volatility, annualized
        rolling_vol = returns.rolling(window=window_days).std() * np.sqrt(252)

        return rolling_vol.dropna()

    @classmethod
    def get_ticker_drawdowns(
        cls,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.Series":
        """
        Calculate drawdown series for a single ticker.

        Returns:
            Series of drawdown values (as negative decimals, e.g., -0.15 = -15%)
        """
        import pandas as pd

        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty:
            return pd.Series(dtype=float)

        # Calculate cumulative returns (wealth index)
        cumulative = (1 + returns).cumprod()

        # Calculate running maximum
        running_max = cumulative.cummax()

        # Drawdown = current / peak - 1
        drawdowns = cumulative / running_max - 1

        return drawdowns

    @classmethod
    def get_ticker_rolling_returns(
        cls,
        ticker: str,
        window_days: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.Series":
        """
        Calculate rolling returns with specified window for a single ticker.
        """
        import pandas as pd

        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty or len(returns) < window_days:
            return pd.Series(dtype=float)

        # Calculate rolling compounded returns
        def compound_return(window):
            return (1 + window).prod() - 1

        rolling_returns = returns.rolling(window=window_days).apply(
            compound_return, raw=False
        )

        return rolling_returns.dropna()

    @classmethod
    def get_ticker_time_under_water(
        cls,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.Series":
        """
        Calculate time under water for a single ticker.

        Returns:
            Series of days under water (integer values)
        """
        import pandas as pd

        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty:
            return pd.Series(dtype=float)

        # Calculate cumulative returns (wealth index)
        cumulative = (1 + returns).cumprod()

        # Calculate running maximum
        running_max = cumulative.cummax()

        # Track days under water
        days_under_water = pd.Series(0, index=cumulative.index, dtype=int)

        current_underwater_days = 0
        for i, (cum, peak) in enumerate(zip(cumulative, running_max)):
            if cum < peak:
                current_underwater_days += 1
            else:
                current_underwater_days = 0
            days_under_water.iloc[i] = current_underwater_days

        return days_under_water
