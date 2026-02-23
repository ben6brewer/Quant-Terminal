"""Live Return Service - Append today's live market return to returns series."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import pandas as pd


class LiveReturnService:
    """Inject today's live return into portfolio or ticker returns series."""

    @classmethod
    def append_live_return(
        cls,
        returns: "pd.Series",
        ticker: str,
    ) -> "pd.Series":
        """
        Append today's live return to a returns series if eligible.

        Only appends if:
        - Today is a trading day (stocks) or any day (crypto)
        - Current time is within extended market hours (stocks) or any time (crypto)
        - Returns series doesn't already include today

        Args:
            returns: Existing returns series with DatetimeIndex
            ticker: Ticker symbol to fetch live price for

        Returns:
            Returns series with today's live return appended (if applicable),
            or original series if not eligible for update
        """
        import pandas as pd
        from app.utils.market_hours import is_crypto_ticker, is_market_open_extended

        if returns is None or returns.empty:
            return returns

        # Check if ticker is eligible for live update
        is_crypto = is_crypto_ticker(ticker)
        if not is_crypto and not is_market_open_extended():
            return returns  # Stocks outside market hours

        # Check if returns already includes today
        today = pd.Timestamp.now().normalize()
        if returns.index.max() >= today:
            return returns  # Already have today's data

        # Get yesterday's close (last value in the price series)
        from app.services.market_data import fetch_price_history

        df = fetch_price_history(ticker, period="5d", interval="1d", skip_live_bar=True)
        if df is None or df.empty or len(df) < 2:
            return returns

        yesterday_close = df["Close"].iloc[-1]

        # Fetch live price
        from app.services.yahoo_finance_service import YahooFinanceService

        live_prices = YahooFinanceService.fetch_batch_current_prices([ticker])
        if not live_prices or ticker not in live_prices:
            return returns

        live_price = live_prices[ticker]

        # Calculate today's return
        todays_return = (live_price / yesterday_close) - 1

        # Append to returns series
        new_entry = pd.Series([todays_return], index=[today], name=returns.name)
        updated_returns = pd.concat([returns, new_entry])

        print(f"[Live Return] {ticker}: yesterday=${yesterday_close:.2f}, live=${live_price:.2f}, return={todays_return:.4f}")

        return updated_returns

    @classmethod
    def append_live_portfolio_return(
        cls,
        returns: "pd.Series",
        portfolio_name: str,
        include_cash: bool = False,
    ) -> "pd.Series":
        """
        Append today's live portfolio return based on current holdings.

        Fetches live prices for all eligible tickers and calculates
        the weighted portfolio return for today.

        Args:
            returns: Existing portfolio returns series
            portfolio_name: Name of the portfolio
            include_cash: Whether to include cash in weight calculation

        Returns:
            Returns series with today's live return appended (if applicable)
        """
        import pandas as pd
        from app.utils.market_hours import is_crypto_ticker, is_market_open_extended
        from app.services.yahoo_finance_service import YahooFinanceService
        from app.services.market_data import fetch_price_history
        from app.services.returns_data_service import ReturnsDataService

        if returns is None or returns.empty:
            return returns

        # Check if returns already includes today
        today = pd.Timestamp.now().normalize()
        if returns.index.max() >= today:
            return returns

        # Get current positions and weights from latest date
        from app.services.position_history_service import PositionHistoryService
        weights = PositionHistoryService.get_daily_weights(portfolio_name, include_cash=include_cash)
        if weights.empty:
            return returns

        # Get latest weights (last row)
        latest_weights = weights.iloc[-1]
        tickers = [t for t in latest_weights.index if t.upper() != "FREE CASH" and latest_weights[t] > 0]

        if not tickers:
            return returns

        # Determine which tickers are eligible for live update
        is_extended_hours = is_market_open_extended()
        eligible_tickers = []
        for ticker in tickers:
            if is_crypto_ticker(ticker) or is_extended_hours:
                eligible_tickers.append(ticker)

        if not eligible_tickers:
            return returns

        # Fetch live prices in batch
        live_prices = YahooFinanceService.fetch_batch_current_prices(eligible_tickers)
        if not live_prices:
            return returns

        # Get yesterday's closes for eligible tickers
        yesterday_closes = {}
        for ticker in eligible_tickers:
            df = fetch_price_history(ticker, period="5d", interval="1d", skip_live_bar=True)
            if df is not None and not df.empty:
                yesterday_closes[ticker] = df["Close"].iloc[-1]

        # Calculate weighted portfolio return for today
        portfolio_return = 0.0
        total_weight = 0.0

        for ticker in eligible_tickers:
            if ticker in live_prices and ticker in yesterday_closes:
                weight = latest_weights[ticker]
                yesterday = yesterday_closes[ticker]
                live = live_prices[ticker]
                ticker_return = (live / yesterday) - 1
                portfolio_return += weight * ticker_return
                total_weight += weight

        if total_weight == 0:
            return returns

        # Append to returns series
        new_entry = pd.Series([portfolio_return], index=[today], name=returns.name)
        updated_returns = pd.concat([returns, new_entry])

        print(f"[Live Return] Portfolio {portfolio_name}: {len(eligible_tickers)} tickers updated, return={portfolio_return:.4f}")

        return updated_returns
