"""Brinson Attribution Service - Performance attribution using Brinson-Fachler methodology.

Implements Brinson-Fachler (1985) attribution analysis to decompose portfolio
excess returns into allocation, selection, and interaction effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    import pandas as pd

from app.services.ishares_holdings_service import ETFHolding


@dataclass
class AttributionResult:
    """Attribution results for a single holding or sector."""

    ticker: str  # Ticker symbol or sector name for aggregated results
    name: str
    sector: str
    industry: str
    portfolio_weight: float  # w_p (decimal)
    benchmark_weight: float  # w_b (decimal)
    portfolio_return: float  # r_p (decimal)
    benchmark_return: float  # r_b (decimal)
    allocation_effect: float  # (w_p - w_b) * (r_b_sector - r_b_total)
    selection_effect: float  # w_b * (r_p - r_b)
    interaction_effect: float  # (w_p - w_b) * (r_p - r_b)
    total_effect: float  # allocation + selection + interaction


@dataclass
class BrinsonAnalysis:
    """Complete Brinson-Fachler analysis results."""

    period_start: str
    period_end: str
    total_portfolio_return: float  # Cumulative return for period
    total_benchmark_return: float
    total_excess_return: float
    total_allocation_effect: float
    total_selection_effect: float
    total_interaction_effect: float

    by_security: Dict[str, AttributionResult] = field(default_factory=dict)
    by_sector: Dict[str, AttributionResult] = field(default_factory=dict)


class BrinsonAttributionService:
    """
    Brinson-Fachler (1985) performance attribution.

    Decomposes portfolio excess return into:
    - Allocation Effect: Return from over/underweighting sectors
    - Selection Effect: Return from security selection within sectors
    - Interaction Effect: Combined effect of allocation and selection decisions
    """

    @classmethod
    def calculate_attribution(
        cls,
        portfolio_weights: Dict[str, float],
        benchmark_holdings: Dict[str, ETFHolding],
        portfolio_returns: "pd.DataFrame",
        benchmark_returns: "pd.DataFrame",
        period_start: str,
        period_end: str,
        daily_weights: "pd.DataFrame" = None,
        daily_benchmark_weights: "pd.DataFrame" = None,
    ) -> BrinsonAnalysis:
        """
        Calculate Brinson-Fachler attribution.

        Args:
            portfolio_weights: Dict mapping ticker -> weight (decimal)
            benchmark_holdings: Dict mapping ticker -> ETFHolding from iShares
            portfolio_returns: DataFrame with tickers as columns, daily returns
            benchmark_returns: DataFrame with benchmark constituent returns
            period_start: Start date (YYYY-MM-DD)
            period_end: End date (YYYY-MM-DD)
            daily_weights: Optional DataFrame with daily portfolio weights.
                          If provided, returns are calculated only for days
                          when each ticker was actually held.
            daily_benchmark_weights: Optional DataFrame with daily benchmark weights
                          from FMP. If provided, uses time-varying benchmark weights
                          for more accurate attribution.

        Returns:
            BrinsonAnalysis with complete attribution breakdown
        """
        import numpy as np

        # Calculate cumulative returns for the period
        # For portfolio: use daily_weights to only count returns when held
        port_cum_returns = cls._calculate_period_returns(
            portfolio_returns, period_start, period_end, weights_df=daily_weights
        )
        # For benchmark: use full period (benchmark weights are static)
        bench_cum_returns = cls._calculate_period_returns(
            benchmark_returns, period_start, period_end
        )

        # Get benchmark weights from holdings (static, for fallback and security-level)
        benchmark_weights = {
            ticker: holding.weight for ticker, holding in benchmark_holdings.items()
        }

        # Calculate total benchmark return
        # Use time-varying weights if available, otherwise static
        if daily_benchmark_weights is not None and not daily_benchmark_weights.empty:
            total_benchmark_return = cls._calculate_time_varying_portfolio_return(
                daily_benchmark_weights, benchmark_returns, period_start, period_end
            )
            print(f"[Attribution] Using time-varying benchmark weights, return: {total_benchmark_return * 100:.2f}%")
        else:
            # Fallback to static weights
            total_benchmark_return = sum(
                benchmark_weights.get(ticker, 0) * bench_cum_returns.get(ticker, 0)
                for ticker in benchmark_weights
            )
            print(f"[Attribution] Using static benchmark weights, return: {total_benchmark_return * 100:.2f}%")

        # Calculate sector-level benchmark returns
        sector_bench_returns = cls._calculate_sector_returns(
            benchmark_holdings, bench_cum_returns
        )

        # Calculate attribution for each security
        security_results: Dict[str, AttributionResult] = {}
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_holdings.keys())

        for ticker in all_tickers:
            port_weight = portfolio_weights.get(ticker, 0)
            bench_weight = benchmark_weights.get(ticker, 0)

            # Portfolio return: use actual return if in portfolio, else 0
            port_return = port_cum_returns.get(ticker, 0) if port_weight > 0 else 0

            # Benchmark return: use actual return ONLY if in benchmark, else 0
            # (Don't use portfolio ticker returns for benchmark calculation)
            bench_return = bench_cum_returns.get(ticker, 0) if bench_weight > 0 else 0

            result = cls._calculate_security_attribution(
                ticker=ticker,
                portfolio_weight=port_weight,
                benchmark_weight=bench_weight,
                portfolio_return=port_return,
                benchmark_return=bench_return,
                benchmark_holdings=benchmark_holdings,
                sector_bench_returns=sector_bench_returns,
                total_benchmark_return=total_benchmark_return,
            )
            if result:
                security_results[ticker] = result

        # Aggregate by sector
        sector_results = cls._aggregate_by_sector(security_results)

        # Calculate totals - use time-varying weights if available
        if daily_weights is not None and not daily_weights.empty:
            # Use time-varying weights for accurate portfolio return
            total_portfolio_return = cls._calculate_time_varying_portfolio_return(
                daily_weights, portfolio_returns, period_start, period_end
            )

            # Get sector ticker weights for daily attribution
            sector_ticker_weights = cls._get_sector_ticker_weights(benchmark_holdings)

            # Calculate daily attribution effects and sum them
            daily_alloc, daily_sel, daily_inter = cls._calculate_daily_attribution(
                daily_weights,
                benchmark_weights,
                sector_ticker_weights,
                portfolio_returns,
                benchmark_returns,
                benchmark_holdings,
                period_start,
                period_end,
                daily_benchmark_weights,
            )

            # Arithmetic linking (sum of daily effects)
            total_allocation = daily_alloc.sum() if len(daily_alloc) > 0 else 0.0
            total_selection = daily_sel.sum() if len(daily_sel) > 0 else 0.0
            total_interaction = daily_inter.sum() if len(daily_inter) > 0 else 0.0
        else:
            # Fallback to static weights (backward compatibility)
            total_portfolio_return = sum(
                portfolio_weights.get(ticker, 0) * port_cum_returns.get(ticker, 0)
                for ticker in portfolio_weights
            )

            # Calculate totals from security-level results
            total_allocation = sum(
                r.allocation_effect for r in security_results.values()
            )
            total_selection = sum(
                r.selection_effect for r in security_results.values()
            )
            total_interaction = sum(
                r.interaction_effect for r in security_results.values()
            )

        return BrinsonAnalysis(
            period_start=period_start,
            period_end=period_end,
            total_portfolio_return=total_portfolio_return,
            total_benchmark_return=total_benchmark_return,
            total_excess_return=total_portfolio_return - total_benchmark_return,
            total_allocation_effect=total_allocation,
            total_selection_effect=total_selection,
            total_interaction_effect=total_interaction,
            by_security=security_results,
            by_sector=sector_results,
        )

    @classmethod
    def _calculate_period_returns(
        cls,
        returns_df: "pd.DataFrame",
        start_date: str,
        end_date: str,
        weights_df: "pd.DataFrame" = None,
    ) -> Dict[str, float]:
        """
        Calculate cumulative returns for each ticker over the period.

        If weights_df is provided, only calculates returns for days when the
        ticker was actually held (weight > 0). This gives accurate holding-period
        returns for securities that were bought/sold during the period.

        Args:
            returns_df: DataFrame with daily returns (tickers as columns)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            weights_df: Optional DataFrame with daily weights (tickers as columns)

        Returns:
            Dict mapping ticker -> cumulative return (decimal)
        """
        import pandas as pd

        if returns_df is None or returns_df.empty:
            return {}

        # Filter to date range
        mask = (returns_df.index >= pd.Timestamp(start_date)) & (
            returns_df.index <= pd.Timestamp(end_date)
        )
        period_returns = returns_df.loc[mask]

        if period_returns.empty:
            return {}

        # Also filter weights if provided (using its own date range, not the returns mask)
        period_weights = None
        if weights_df is not None and not weights_df.empty:
            weights_mask = (weights_df.index >= pd.Timestamp(start_date)) & (
                weights_df.index <= pd.Timestamp(end_date)
            )
            period_weights = weights_df.loc[weights_mask] if weights_mask.any() else None

        # Calculate cumulative return: (1 + r1) * (1 + r2) * ... - 1
        # If weights provided, only include days when ticker was held (weight > 0)
        cum_returns = {}
        for ticker in period_returns.columns:
            series = period_returns[ticker].dropna()

            # If we have weights, filter to only days when ticker was held
            if period_weights is not None and ticker in period_weights.columns:
                ticker_weights = period_weights[ticker]
                # Only include days where weight > 0 (ticker was held)
                held_dates = ticker_weights[ticker_weights > 0].index
                series = series[series.index.isin(held_dates)]

            if len(series) > 0:
                cum_return = (1 + series).prod() - 1
                cum_returns[ticker] = cum_return

        return cum_returns

    @classmethod
    def _calculate_time_varying_portfolio_return(
        cls,
        daily_weights: "pd.DataFrame",
        ticker_returns: "pd.DataFrame",
        period_start: str,
        period_end: str,
    ) -> float:
        """
        Calculate portfolio return using time-varying weights.

        This matches how Performance Metrics calculates returns:
        - Daily: portfolio_return_t = sum(w_i,t * r_i,t)
        - Total: (1 + r_1) * (1 + r_2) * ... - 1

        Args:
            daily_weights: DataFrame with daily portfolio weights (tickers as columns)
            ticker_returns: DataFrame with daily returns (tickers as columns)
            period_start: Start date (YYYY-MM-DD)
            period_end: End date (YYYY-MM-DD)

        Returns:
            Total portfolio return as decimal
        """
        import pandas as pd

        if daily_weights is None or daily_weights.empty:
            return 0.0
        if ticker_returns is None or ticker_returns.empty:
            return 0.0

        # Filter to period
        start = pd.Timestamp(period_start)
        end = pd.Timestamp(period_end)

        weights = daily_weights[
            (daily_weights.index >= start) & (daily_weights.index <= end)
        ]
        returns = ticker_returns[
            (ticker_returns.index >= start) & (ticker_returns.index <= end)
        ]

        if weights.empty or returns.empty:
            return 0.0

        # Align indices
        common_dates = weights.index.intersection(returns.index)
        if common_dates.empty:
            return 0.0

        weights = weights.loc[common_dates]
        returns = returns.loc[common_dates]

        # DEBUG: Print diagnostic information
        print("\n" + "=" * 50)
        print("=== RISK ANALYTICS ATTRIBUTION DEBUG ===")
        print("=" * 50)
        print(f"Period: {period_start} to {period_end}")
        print(f"Daily weights shape: {weights.shape}")
        print(f"Ticker returns shape: {returns.shape}")
        print(f"Common dates: {len(common_dates)} days")
        print(f"  First date: {common_dates[0] if len(common_dates) > 0 else 'N/A'}")
        print(f"  Last date: {common_dates[-1] if len(common_dates) > 0 else 'N/A'}")
        print(f"Tickers in weights: {list(weights.columns)}")
        print(f"Tickers in returns: {list(returns.columns)}")

        # Check weight sums
        weight_sums = weights.sum(axis=1)
        print(f"Weight sum (first 3 days): {weight_sums.head(3).tolist()}")
        print(f"Weight sum (last 3 days): {weight_sums.tail(3).tolist()}")

        # Sample weights for first ticker
        if len(weights.columns) > 0:
            first_ticker = weights.columns[0]
            print(f"Sample weights for {first_ticker} (first 3): {weights[first_ticker].head(3).tolist()}")

        # Sample returns for first ticker
        if len(returns.columns) > 0:
            first_ticker = returns.columns[0]
            print(f"Sample returns for {first_ticker} (first 3): {returns[first_ticker].head(3).tolist()}")

        # Calculate daily weighted portfolio returns
        daily_portfolio_returns = pd.Series(0.0, index=common_dates)
        for ticker in weights.columns:
            if ticker in returns.columns:
                ticker_returns_series = returns[ticker].fillna(0)
                ticker_weights = weights[ticker].fillna(0)
                daily_portfolio_returns += ticker_weights * ticker_returns_series

        # DEBUG: Print daily portfolio returns
        print(f"Daily portfolio returns (first 5): {daily_portfolio_returns.head(5).tolist()}")
        print(f"Daily portfolio returns (last 5): {daily_portfolio_returns.tail(5).tolist()}")
        print(f"Daily portfolio returns mean: {daily_portfolio_returns.mean():.6f}")
        print(f"Daily portfolio returns std: {daily_portfolio_returns.std():.6f}")

        # Compound to total return: (1 + r1) * (1 + r2) * ... - 1
        total_return = (1 + daily_portfolio_returns).prod() - 1

        # DEBUG: Print final return
        print(f"Final compounded return: {total_return * 100:.4f}%")
        print("=" * 50 + "\n")

        return total_return

    @classmethod
    def _calculate_sector_returns(
        cls,
        benchmark_holdings: Dict[str, ETFHolding],
        benchmark_returns: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Calculate weighted sector-level benchmark returns.

        Args:
            benchmark_holdings: Dict of ETF holdings
            benchmark_returns: Dict of ticker -> cumulative return

        Returns:
            Dict mapping sector -> weighted return
        """
        sector_weights: Dict[str, float] = {}
        sector_returns: Dict[str, float] = {}

        for ticker, holding in benchmark_holdings.items():
            sector = holding.sector
            weight = holding.weight
            ret = benchmark_returns.get(ticker, 0)

            if sector not in sector_weights:
                sector_weights[sector] = 0
                sector_returns[sector] = 0

            sector_weights[sector] += weight
            sector_returns[sector] += weight * ret

        # Normalize by sector weight
        for sector in sector_returns:
            if sector_weights[sector] > 0:
                sector_returns[sector] /= sector_weights[sector]

        return sector_returns

    @classmethod
    def _get_sector_ticker_weights(
        cls,
        benchmark_holdings: Dict[str, ETFHolding],
    ) -> Dict[str, Dict[str, float]]:
        """
        Group benchmark tickers by sector with their weights.

        Args:
            benchmark_holdings: Dict of ETF holdings

        Returns:
            Dict mapping sector -> {ticker -> weight}
        """
        sector_tickers: Dict[str, Dict[str, float]] = {}

        for ticker, holding in benchmark_holdings.items():
            sector = holding.sector
            weight = holding.weight

            if sector not in sector_tickers:
                sector_tickers[sector] = {}

            sector_tickers[sector][ticker] = weight

        return sector_tickers

    @classmethod
    def _calculate_daily_attribution(
        cls,
        daily_portfolio_weights: "pd.DataFrame",
        benchmark_weights: Dict[str, float],
        sector_ticker_weights: Dict[str, Dict[str, float]],
        portfolio_returns: "pd.DataFrame",
        benchmark_returns: "pd.DataFrame",
        benchmark_holdings: Dict[str, ETFHolding],
        period_start: str,
        period_end: str,
        daily_benchmark_weights: "pd.DataFrame" = None,
    ) -> Tuple["pd.Series", "pd.Series", "pd.Series"]:
        """
        Calculate daily Brinson attribution effects.

        For each day t:
        - Allocation_t = sum[(w_p,i,t - w_b,i,t) * (r_b,sector,t - r_b,total,t)]
        - Selection_t = sum[w_b,i,t * (r_p,i,t - r_b,i,t)]
        - Interaction_t = sum[(w_p,i,t - w_b,i,t) * (r_p,i,t - r_b,i,t)]

        Args:
            daily_portfolio_weights: DataFrame with daily portfolio weights
            benchmark_weights: Dict of static benchmark weights {ticker -> weight}
            sector_ticker_weights: Dict of sector -> {ticker -> weight}
            portfolio_returns: Daily returns for portfolio tickers
            benchmark_returns: Daily returns for benchmark constituents
            benchmark_holdings: Dict of ETF holdings for sector lookup
            period_start: Start date
            period_end: End date
            daily_benchmark_weights: Optional DataFrame with daily benchmark weights
                                    from FMP. If provided, uses time-varying weights.

        Returns:
            Tuple of (allocation_series, selection_series, interaction_series)
        """
        import pandas as pd
        import numpy as np

        # Filter to period
        start = pd.Timestamp(period_start)
        end = pd.Timestamp(period_end)

        port_weights = daily_portfolio_weights[
            (daily_portfolio_weights.index >= start)
            & (daily_portfolio_weights.index <= end)
        ]

        port_returns = portfolio_returns[
            (portfolio_returns.index >= start) & (portfolio_returns.index <= end)
        ]

        bench_returns = benchmark_returns[
            (benchmark_returns.index >= start) & (benchmark_returns.index <= end)
        ]

        # Filter daily benchmark weights if provided
        bench_weights_df = None
        use_time_varying_bench = False
        if daily_benchmark_weights is not None and not daily_benchmark_weights.empty:
            bench_weights_df = daily_benchmark_weights[
                (daily_benchmark_weights.index >= start)
                & (daily_benchmark_weights.index <= end)
            ]
            use_time_varying_bench = not bench_weights_df.empty

        # Find common dates across all data sources
        common_dates = (
            port_weights.index.intersection(port_returns.index).intersection(
                bench_returns.index
            )
        )

        if common_dates.empty:
            empty_series = pd.Series(dtype=float)
            return empty_series, empty_series, empty_series

        # Initialize daily effects
        daily_allocation = pd.Series(0.0, index=common_dates)
        daily_selection = pd.Series(0.0, index=common_dates)
        daily_interaction = pd.Series(0.0, index=common_dates)

        # Pre-calculate sector total weights for daily sector return calculation
        # Note: For sector returns, we still use static weights as we don't have
        # historical sector assignments from FMP
        sector_total_weights: Dict[str, float] = {}
        for sector, tickers in sector_ticker_weights.items():
            sector_total_weights[sector] = sum(tickers.values())

        # Calculate daily effects
        for date in common_dates:
            # Calculate benchmark total return for this day
            bench_total_return = 0.0
            for ticker, weight in benchmark_weights.items():
                if ticker in bench_returns.columns:
                    ret = bench_returns.loc[date, ticker]
                    if pd.notna(ret):
                        bench_total_return += weight * ret

            # Calculate sector returns for this day
            sector_returns_today: Dict[str, float] = {}
            for sector, tickers in sector_ticker_weights.items():
                sector_return = 0.0
                for ticker, weight in tickers.items():
                    if ticker in bench_returns.columns:
                        ret = bench_returns.loc[date, ticker]
                        if pd.notna(ret):
                            sector_return += weight * ret
                # Normalize by sector total weight
                if sector_total_weights[sector] > 0:
                    sector_returns_today[sector] = (
                        sector_return / sector_total_weights[sector]
                    )
                else:
                    sector_returns_today[sector] = 0.0

            # Calculate effects for each security
            all_tickers = set(port_weights.columns) | set(benchmark_weights.keys())

            for ticker in all_tickers:
                # Portfolio weight (time-varying)
                w_p = 0.0
                if ticker in port_weights.columns:
                    w_p_val = port_weights.loc[date, ticker]
                    if pd.notna(w_p_val):
                        w_p = w_p_val

                # Benchmark weight (time-varying if available, else static)
                w_b = 0.0
                if use_time_varying_bench and ticker in bench_weights_df.columns:
                    if date in bench_weights_df.index:
                        w_b_val = bench_weights_df.loc[date, ticker]
                        if pd.notna(w_b_val):
                            w_b = w_b_val
                else:
                    w_b = benchmark_weights.get(ticker, 0.0)

                # Portfolio return
                r_p = 0.0
                if ticker in port_returns.columns:
                    r_p_val = port_returns.loc[date, ticker]
                    if pd.notna(r_p_val):
                        r_p = r_p_val

                # Benchmark return
                r_b = 0.0
                if ticker in bench_returns.columns:
                    r_b_val = bench_returns.loc[date, ticker]
                    if pd.notna(r_b_val):
                        r_b = r_b_val

                # Get sector benchmark return
                if ticker in benchmark_holdings:
                    sector = benchmark_holdings[ticker].sector
                else:
                    sector = "Not Classified"
                r_b_sector = sector_returns_today.get(sector, bench_total_return)

                # Brinson-Fachler formulas
                active_weight = w_p - w_b
                daily_allocation[date] += active_weight * (
                    r_b_sector - bench_total_return
                )
                daily_selection[date] += w_b * (r_p - r_b)
                daily_interaction[date] += active_weight * (r_p - r_b)

        return daily_allocation, daily_selection, daily_interaction

    @classmethod
    def _calculate_security_attribution(
        cls,
        ticker: str,
        portfolio_weight: float,
        benchmark_weight: float,
        portfolio_return: float,
        benchmark_return: float,
        benchmark_holdings: Dict[str, ETFHolding],
        sector_bench_returns: Dict[str, float],
        total_benchmark_return: float,
    ) -> Optional[AttributionResult]:
        """
        Calculate Brinson attribution for a single security.

        Brinson-Fachler (1985) formulas:
        - Allocation = (w_p - w_b) * (r_b_sector - r_b_total)
        - Selection = w_b * (r_p - r_b)
        - Interaction = (w_p - w_b) * (r_p - r_b)
        """
        from app.services.ticker_metadata_service import TickerMetadataService

        # Skip if no exposure
        if portfolio_weight == 0 and benchmark_weight == 0:
            return None

        # Get sector and industry
        if ticker in benchmark_holdings:
            holding = benchmark_holdings[ticker]
            sector = holding.sector
            name = holding.name
            industry = ""  # iShares doesn't provide industry
        else:
            # Non-benchmark holding - use Yahoo metadata
            metadata = TickerMetadataService.get_metadata(ticker)
            sector = metadata.get("sector", "Not Classified")
            name = metadata.get("shortName", ticker)
            industry = metadata.get("industry", "")

        # Get sector benchmark return
        sector_bench_return = sector_bench_returns.get(sector, total_benchmark_return)

        # Brinson-Fachler formulas
        active_weight = portfolio_weight - benchmark_weight
        allocation_effect = active_weight * (sector_bench_return - total_benchmark_return)
        selection_effect = benchmark_weight * (portfolio_return - benchmark_return)
        interaction_effect = active_weight * (portfolio_return - benchmark_return)
        total_effect = allocation_effect + selection_effect + interaction_effect

        return AttributionResult(
            ticker=ticker,
            name=name,
            sector=sector,
            industry=industry,
            portfolio_weight=portfolio_weight,
            benchmark_weight=benchmark_weight,
            portfolio_return=portfolio_return,
            benchmark_return=benchmark_return,
            allocation_effect=allocation_effect,
            selection_effect=selection_effect,
            interaction_effect=interaction_effect,
            total_effect=total_effect,
        )

    @classmethod
    def _aggregate_by_sector(
        cls,
        security_results: Dict[str, AttributionResult],
    ) -> Dict[str, AttributionResult]:
        """
        Aggregate security-level attribution to sector level.

        Args:
            security_results: Dict of ticker -> AttributionResult

        Returns:
            Dict of sector -> aggregated AttributionResult
        """
        sector_data: Dict[str, Dict] = {}

        for ticker, result in security_results.items():
            sector = result.sector

            if sector not in sector_data:
                sector_data[sector] = {
                    "portfolio_weight": 0,
                    "benchmark_weight": 0,
                    "portfolio_return_weighted": 0,
                    "benchmark_return_weighted": 0,
                    "allocation_effect": 0,
                    "selection_effect": 0,
                    "interaction_effect": 0,
                    "count": 0,
                }

            data = sector_data[sector]
            data["portfolio_weight"] += result.portfolio_weight
            data["benchmark_weight"] += result.benchmark_weight
            data["portfolio_return_weighted"] += (
                result.portfolio_weight * result.portfolio_return
            )
            data["benchmark_return_weighted"] += (
                result.benchmark_weight * result.benchmark_return
            )
            data["allocation_effect"] += result.allocation_effect
            data["selection_effect"] += result.selection_effect
            data["interaction_effect"] += result.interaction_effect
            data["count"] += 1

        # Create aggregated results
        sector_results: Dict[str, AttributionResult] = {}

        for sector, data in sector_data.items():
            # Calculate weighted average returns
            port_ret = (
                data["portfolio_return_weighted"] / data["portfolio_weight"]
                if data["portfolio_weight"] > 0
                else 0
            )
            bench_ret = (
                data["benchmark_return_weighted"] / data["benchmark_weight"]
                if data["benchmark_weight"] > 0
                else 0
            )

            total_effect = (
                data["allocation_effect"]
                + data["selection_effect"]
                + data["interaction_effect"]
            )

            sector_results[sector] = AttributionResult(
                ticker=sector,  # Use sector name as "ticker" for display
                name=f"{sector} ({data['count']} holdings)",
                sector=sector,
                industry="",
                portfolio_weight=data["portfolio_weight"],
                benchmark_weight=data["benchmark_weight"],
                portfolio_return=port_ret,
                benchmark_return=bench_ret,
                allocation_effect=data["allocation_effect"],
                selection_effect=data["selection_effect"],
                interaction_effect=data["interaction_effect"],
                total_effect=total_effect,
            )

        return sector_results
