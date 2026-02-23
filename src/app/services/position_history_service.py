"""Position History Service - Reconstruct positions and weights from transactions."""

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd

from app.services.portfolio_data_service import PortfolioDataService


class PositionHistoryService:
    """Reconstruct position quantities and market-value weights over time."""

    @classmethod
    def get_position_history(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = True,
    ) -> "pd.DataFrame":
        """
        Reconstruct position quantities for each date from transaction history.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH positions

        Returns:
            DataFrame with dates as index, tickers as columns, quantities as values.
        """
        import pandas as pd

        transactions = PortfolioDataService.get_transactions(portfolio_name)
        if not transactions:
            return pd.DataFrame()

        if not include_cash:
            transactions = [t for t in transactions if t.ticker.upper() != "FREE CASH"]

        if not transactions:
            return pd.DataFrame()

        transactions = sorted(transactions, key=lambda t: (t.date, t.sequence))

        tickers = list(set(t.ticker for t in transactions))

        # Build position changes by date
        position_changes: Dict[str, Dict[str, float]] = {}

        for tx in transactions:
            date = tx.date
            ticker = tx.ticker

            if date not in position_changes:
                position_changes[date] = {}

            if ticker not in position_changes[date]:
                position_changes[date][ticker] = 0.0

            if tx.transaction_type == "Buy":
                position_changes[date][ticker] += tx.quantity
            else:
                position_changes[date][ticker] -= tx.quantity

        transaction_dates = sorted(position_changes.keys())
        if not transaction_dates:
            return pd.DataFrame()

        first_tx_date = pd.to_datetime(transaction_dates[0])

        if end_date:
            last_date = pd.to_datetime(end_date)
        else:
            last_date = pd.Timestamp.now().normalize()

        all_dates = pd.date_range(start=first_tx_date, end=last_date, freq="D")

        positions = pd.DataFrame(0.0, index=all_dates, columns=tickers)

        current_position = {ticker: 0.0 for ticker in tickers}

        for date in all_dates:
            date_str = date.strftime("%Y-%m-%d")

            if date_str in position_changes:
                for ticker, change in position_changes[date_str].items():
                    current_position[ticker] += change

            for ticker in tickers:
                positions.loc[date, ticker] = current_position[ticker]

        if start_date:
            positions = positions[positions.index >= pd.to_datetime(start_date)]

        return positions

    @classmethod
    def get_daily_weights(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = True,
    ) -> "pd.DataFrame":
        """
        Calculate portfolio weights for each date based on market values.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH with weight contribution

        Returns:
            DataFrame with dates as index, tickers as columns, weights as values.
        """
        import numpy as np
        import pandas as pd

        positions = cls.get_position_history(
            portfolio_name, start_date, end_date, include_cash
        )
        if positions.empty:
            return pd.DataFrame()

        tickers = positions.columns.tolist()

        from app.services.market_data import fetch_price_history_batch

        tickers_to_fetch = [t for t in tickers if t.upper() != "FREE CASH"]
        batch_data = fetch_price_history_batch(tickers_to_fetch)

        price_data: Dict[str, Any] = {}
        for ticker in tickers_to_fetch:
            if ticker in batch_data:
                df = batch_data[ticker]
                if df is not None and not df.empty:
                    close = df["Close"]
                    close.index = pd.to_datetime(close.index)
                    price_data[ticker] = close

        market_values = pd.DataFrame(index=positions.index, columns=tickers, dtype=float)

        for ticker in tickers:
            if ticker.upper() == "FREE CASH":
                market_values[ticker] = positions[ticker]
            elif ticker in price_data:
                prices = price_data[ticker].reindex(positions.index, method="ffill")
                market_values[ticker] = positions[ticker] * prices
            else:
                market_values[ticker] = 0.0

        market_values = market_values.fillna(0)

        total_values = market_values.sum(axis=1)

        weights = market_values.copy()
        for col in weights.columns:
            weights[col] = np.where(
                total_values > 0,
                market_values[col] / total_values,
                0.0
            )

        return weights
