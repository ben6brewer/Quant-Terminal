"""Frontier Calculation Service - All math for EF, correlation, and covariance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Any, List, Optional

if TYPE_CHECKING:
    import pandas as pd


class FrontierCalculationService:
    """Stateless service for efficient frontier and matrix calculations.

    All methods use lazy imports for heavy libraries (numpy, scipy, pandas).
    """

    @staticmethod
    def compute_daily_returns(
        tickers: List[str],
        lookback_days: Optional[int] = 1825,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> tuple["pd.DataFrame", "pd.DataFrame"]:
        """Fetch price data and compute daily returns for given tickers.

        Returns (prices, daily_returns) DataFrames aligned to common dates.
        Custom date range (start_date/end_date as ISO strings) takes priority
        over lookback_days.
        """
        import pandas as pd
        from app.services.market_data import fetch_price_history_batch

        results = fetch_price_history_batch(tickers)

        price_data = {}
        for ticker in tickers:
            df = results.get(ticker)
            if df is not None and not df.empty:
                close = df["Close"]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                close.index = pd.to_datetime(close.index)
                price_data[ticker] = close

        if not price_data:
            return pd.DataFrame(), pd.DataFrame()

        prices = pd.DataFrame(price_data)

        if start_date is not None and end_date is not None:
            prices = prices.loc[
                (prices.index >= pd.Timestamp(start_date))
                & (prices.index <= pd.Timestamp(end_date))
            ]
        elif lookback_days is not None:
            cutoff = prices.index.max() - pd.Timedelta(days=lookback_days)
            prices = prices.loc[prices.index >= cutoff]

        prices = prices.dropna()
        daily_returns = prices.pct_change().dropna()

        return prices, daily_returns

    @staticmethod
    def get_risk_free_rate() -> float:
        """Get annualized risk-free rate from StatisticsService."""
        from app.services.statistics_service import StatisticsService
        return StatisticsService.get_risk_free_rate()

    @staticmethod
    def calculate_efficient_frontier(
        tickers: List[str],
        num_simulations: int = 10000,
        lookback_days: Optional[int] = 1825,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate efficient frontier with Monte Carlo simulation.

        Returns dict with frontier curve, simulation scatter, special portfolios,
        individual asset points, and CML data.
        """
        import numpy as np
        from scipy.optimize import minimize

        prices, daily_returns = FrontierCalculationService.compute_daily_returns(
            tickers, lookback_days, start_date=start_date, end_date=end_date
        )

        if daily_returns.empty or len(daily_returns) < 30:
            raise ValueError(
                f"Insufficient data: need at least 30 trading days, got {len(daily_returns)}"
            )

        # Filter tickers to only those with data
        tickers = list(daily_returns.columns)
        num_assets = len(tickers)

        if num_assets < 2:
            raise ValueError("Need at least 2 tickers with valid data")

        # CAGR-based expected returns (more accurate than mean * 252)
        num_years = len(prices) / 252
        cagr = (prices.iloc[-1] / prices.iloc[0]) ** (1 / num_years) - 1
        mean_returns = cagr

        # Annualized covariance matrix
        cov_matrix = daily_returns.cov() * 252

        cov_values = cov_matrix.values
        mean_values = mean_returns.values

        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_values, weights)))

        def portfolio_return(weights):
            return np.dot(weights, mean_values)

        def neg_sharpe_ratio(weights, rf):
            ret = portfolio_return(weights)
            vol = portfolio_volatility(weights)
            if vol < 1e-10:
                return 0.0
            return -(ret - rf) / vol

        # Monte Carlo simulation with Dirichlet weights
        risk_free_rate = FrontierCalculationService.get_risk_free_rate()

        sim_returns = []
        sim_volatilities = []
        sim_sharpe_ratios = []

        # Log-uniform alpha for varying concentration
        alphas = 10 ** np.random.uniform(-2, 0.7, size=num_simulations)

        for alpha in alphas:
            weights = np.random.dirichlet(np.ones(num_assets) * alpha)
            ret = portfolio_return(weights)
            vol = portfolio_volatility(weights)
            sharpe = (ret - risk_free_rate) / vol if vol > 1e-10 else 0.0

            sim_returns.append(ret)
            sim_volatilities.append(vol)
            sim_sharpe_ratios.append(sharpe)

        # SLSQP optimization
        constraints = {"type": "eq", "fun": lambda x: np.sum(x) - 1}
        bounds = tuple((0, 1) for _ in range(num_assets))
        initial_weights = np.array([1 / num_assets] * num_assets)

        # Minimum volatility portfolio
        min_vol_result = minimize(
            portfolio_volatility,
            initial_weights,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )
        min_vol_ret = portfolio_return(min_vol_result.x)
        min_vol_weights = min_vol_result.x
        min_vol_vol = portfolio_volatility(min_vol_weights)

        # Efficient frontier curve (50 points)
        max_ret = float(mean_returns.max())
        target_returns = np.linspace(min_vol_ret, max_ret, 50)
        frontier_volatilities = []
        frontier_returns = []

        for target in target_returns:
            cons = [
                {"type": "eq", "fun": lambda x: np.sum(x) - 1},
                {"type": "eq", "fun": lambda x, t=target: portfolio_return(x) - t},
            ]
            result = minimize(
                portfolio_volatility,
                initial_weights,
                method="SLSQP",
                bounds=bounds,
                constraints=cons,
            )
            if result.success:
                frontier_volatilities.append(portfolio_volatility(result.x))
                frontier_returns.append(target)

        # Tangency portfolio (max Sharpe)
        tangency_result = minimize(
            neg_sharpe_ratio,
            initial_weights,
            args=(risk_free_rate,),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )
        tangency_weights = tangency_result.x
        tangency_vol = portfolio_volatility(tangency_weights)
        tangency_ret = portfolio_return(tangency_weights)
        sharpe_ratio = (
            (tangency_ret - risk_free_rate) / tangency_vol
            if tangency_vol > 1e-10
            else 0.0
        )

        # Max Sortino portfolio
        daily_rf = risk_free_rate / 252

        def neg_sortino_ratio(weights):
            port_daily = daily_returns.values @ weights
            downside = port_daily[port_daily < daily_rf] - daily_rf
            downside_dev = np.sqrt(np.mean(downside ** 2)) * np.sqrt(252)
            if downside_dev < 1e-10:
                return 0.0
            ret = portfolio_return(weights)
            return -(ret - risk_free_rate) / downside_dev

        sortino_result = minimize(
            neg_sortino_ratio,
            initial_weights,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )
        sortino_weights = sortino_result.x
        sortino_vol = portfolio_volatility(sortino_weights)
        sortino_ret = portfolio_return(sortino_weights)
        sortino_ratio = -neg_sortino_ratio(sortino_weights)

        # Individual asset points
        individual_vols = [np.sqrt(cov_matrix.iloc[i, i]) for i in range(num_assets)]
        individual_rets = mean_values.tolist()

        return {
            "frontier_vols": frontier_volatilities,
            "frontier_rets": frontier_returns,
            "sim_vols": sim_volatilities,
            "sim_rets": sim_returns,
            "sim_sharpes": sim_sharpe_ratios,
            "tangency_vol": tangency_vol,
            "tangency_ret": tangency_ret,
            "tangency_weights": tangency_weights.tolist(),
            "sharpe_ratio": sharpe_ratio,
            "sortino_weights": sortino_weights.tolist(),
            "sortino_vol": sortino_vol,
            "sortino_ret": sortino_ret,
            "sortino_ratio": sortino_ratio,
            "min_vol_weights": min_vol_weights.tolist(),
            "min_vol_vol": min_vol_vol,
            "min_vol_ret": min_vol_ret,
            "risk_free_rate": risk_free_rate,
            "individual_vols": individual_vols,
            "individual_rets": individual_rets,
            "tickers": tickers,
            "cov_matrix": cov_values.tolist(),
            "mean_returns": mean_values.tolist(),
        }

    @staticmethod
    def calculate_optimal_portfolio(
        gamma: float,
        cov_matrix: List[List[float]],
        mean_returns: List[float],
    ) -> Dict[str, Any]:
        """Find the portfolio that maximizes mean-variance utility U = E(r) - (γ/2)σ².

        Args:
            gamma: Risk aversion coefficient (> 0)
            cov_matrix: Annualized covariance matrix (nested list)
            mean_returns: Annualized expected returns (list)

        Returns dict with optimal_vol, optimal_ret, optimal_weights, utility.
        """
        import numpy as np
        from scipy.optimize import minimize

        cov = np.array(cov_matrix)
        mu = np.array(mean_returns)
        n = len(mu)

        def neg_utility(weights):
            ret = np.dot(weights, mu)
            vol_sq = np.dot(weights.T, np.dot(cov, weights))
            return -(ret - (gamma / 2) * vol_sq)

        constraints = {"type": "eq", "fun": lambda x: np.sum(x) - 1}
        bounds = tuple((0, 1) for _ in range(n))
        initial = np.array([1 / n] * n)

        result = minimize(
            neg_utility, initial, method="SLSQP",
            bounds=bounds, constraints=constraints,
        )

        w = result.x
        opt_ret = float(np.dot(w, mu))
        opt_vol = float(np.sqrt(np.dot(w.T, np.dot(cov, w))))
        utility = opt_ret - (gamma / 2) * opt_vol ** 2

        return {
            "optimal_vol": opt_vol,
            "optimal_ret": opt_ret,
            "optimal_weights": w.tolist(),
            "utility": utility,
        }

    @staticmethod
    def calculate_correlation_matrix(
        tickers: List[str],
        lookback_days: Optional[int] = 1825,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.DataFrame":
        """Calculate the Pearson correlation matrix for the given tickers."""
        _, daily_returns = FrontierCalculationService.compute_daily_returns(
            tickers, lookback_days, start_date=start_date, end_date=end_date
        )
        if daily_returns.empty:
            raise ValueError("No data available for the selected tickers")
        return daily_returns.corr()

    @staticmethod
    def calculate_covariance_matrix(
        tickers: List[str],
        lookback_days: Optional[int] = 1825,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.DataFrame":
        """Calculate the annualized covariance matrix for the given tickers."""
        _, daily_returns = FrontierCalculationService.compute_daily_returns(
            tickers, lookback_days, start_date=start_date, end_date=end_date
        )
        if daily_returns.empty:
            raise ValueError("No data available for the selected tickers")
        return daily_returns.cov() * 252
