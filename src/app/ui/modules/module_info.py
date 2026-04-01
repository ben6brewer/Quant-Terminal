"""Central module info registry — description, calculation, and data sources for every module."""

from __future__ import annotations

from typing import Optional


MODULE_INFO: dict[str, dict] = {

    # ── Charting ──────────────────────────────────────────────────────────────

    "ChartModule": {
        "title": "Price Charts",
        "description": (
            "Interactive candlestick and line charts for any ticker symbol. "
            "Supports multiple intervals (daily, weekly, monthly, yearly), "
            "logarithmic scaling, and technical overlays."
        ),
        "calculation": (
            "OHLCV data is fetched directly from Yahoo Finance. Candlestick bars show "
            "open, high, low, and close for each period. Volume is displayed as a "
            "secondary bar chart. Technical indicators are computed from price data."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Any valid Yahoo Finance symbol", "frequency": "Daily / Weekly / Monthly"},
        ],
        "source": "Yahoo Finance",
    },

    # ── Portfolio ─────────────────────────────────────────────────────────────

    "PortfolioConstructionModule": {
        "title": "Portfolio Construction",
        "description": (
            "Build and manage multi-asset portfolios with transaction tracking. "
            "View real-time valuations, allocation weights, cost basis, and P&L."
        ),
        "calculation": (
            "Portfolio value is computed as the sum of (shares x current price) for each holding. "
            "Cost basis uses actual transaction prices. Returns are calculated as time-weighted "
            "total returns including dividends."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Portfolio holdings via yfinance", "frequency": "Real-time / Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "PerformanceMetricsModule": {
        "title": "Performance Metrics",
        "description": (
            "Comprehensive performance analytics for a portfolio versus its benchmark. "
            "Includes cumulative returns, drawdowns, rolling returns, and risk-adjusted metrics."
        ),
        "calculation": (
            "Sharpe ratio = (portfolio return - risk-free rate) / portfolio std dev. "
            "Sortino ratio uses downside deviation only. Max drawdown measures the largest "
            "peak-to-trough decline. Alpha and beta from OLS regression against the benchmark."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Portfolio and benchmark prices", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "RiskAnalyticsModule": {
        "title": "Risk Analytics",
        "description": (
            "Portfolio risk decomposition including Value at Risk (VaR), "
            "Conditional VaR (CVaR), volatility analysis, and tail risk metrics."
        ),
        "calculation": (
            "VaR is computed at the 95% and 99% confidence levels using historical simulation. "
            "CVaR (Expected Shortfall) is the mean of losses exceeding VaR. "
            "Rolling volatility uses a 21-day window of annualized standard deviation."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Portfolio and benchmark prices", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "ReturnDistributionModule": {
        "title": "Return Distribution",
        "description": (
            "Statistical analysis of portfolio return distributions. "
            "Visualizes histograms, Q-Q plots, and fits normal and Student-t distributions."
        ),
        "calculation": (
            "Skewness measures asymmetry of returns (negative = left tail risk). "
            "Kurtosis measures tail heaviness (excess kurtosis > 0 = fat tails). "
            "Jarque-Bera test checks for normality."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Portfolio and benchmark returns", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "MonteCarloModule": {
        "title": "Monte Carlo Simulation",
        "description": (
            "Forward-looking portfolio projections using Monte Carlo methods. "
            "Simulates thousands of possible return paths to estimate the "
            "probability distribution of future portfolio values."
        ),
        "calculation": (
            "Generates N simulated return paths using geometric Brownian motion "
            "calibrated to historical mean and volatility. Outputs percentile bands "
            "(5th, 25th, 50th, 75th, 95th) for projected portfolio value over time."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Portfolio historical returns", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    # ── Analysis ──────────────────────────────────────────────────────────────

    "EfficientFrontierModule": {
        "title": "Efficient Frontier",
        "description": (
            "Mean-variance optimization showing the set of optimal portfolios "
            "that offer the highest expected return for each level of risk."
        ),
        "calculation": (
            "Solves the Markowitz optimization: minimize portfolio variance subject to "
            "a target return, using the sample covariance matrix of asset returns. "
            "The capital market line extends from the risk-free rate through the tangency portfolio."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Asset prices for covariance estimation", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "CorrelationMatrixModule": {
        "title": "Correlation Matrix",
        "description": (
            "Heatmap of pairwise Pearson correlation coefficients between assets. "
            "Shows how closely asset returns move together over a chosen time window."
        ),
        "calculation": (
            "Pearson correlation = cov(X,Y) / (std(X) * std(Y)), computed on "
            "log returns over the selected lookback period. Values range from -1 "
            "(perfect inverse) to +1 (perfect co-movement)."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Asset prices", "frequency": "Daily / Weekly / Monthly"},
        ],
        "source": "Yahoo Finance",
    },

    "CovarianceMatrixModule": {
        "title": "Covariance Matrix",
        "description": (
            "Heatmap of pairwise covariance between asset returns. "
            "Unlike correlation, covariance retains information about the magnitude of variability."
        ),
        "calculation": (
            "Sample covariance = E[(X - mean_X)(Y - mean_Y)] computed on "
            "log returns. Diagonal elements represent individual asset variances."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Asset prices", "frequency": "Daily / Weekly / Monthly"},
        ],
        "source": "Yahoo Finance",
    },

    "RollingCorrelationModule": {
        "title": "Rolling Correlation",
        "description": (
            "Time series of rolling pairwise correlation between two assets. "
            "Reveals how the relationship between assets changes over time."
        ),
        "calculation": (
            "Pearson correlation computed over a rolling window (default 60 days). "
            "Each point represents the correlation of the trailing N-day returns."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Two asset price series", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "RollingCovarianceModule": {
        "title": "Rolling Covariance",
        "description": (
            "Time series of rolling pairwise covariance between two assets. "
            "Shows how the joint variability of returns evolves over time."
        ),
        "calculation": (
            "Sample covariance computed over a rolling window (default 60 days). "
            "Each point represents the covariance of the trailing N-day returns."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Two asset price series", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "OLSRegressionModule": {
        "title": "OLS Regression",
        "description": (
            "Ordinary Least Squares regression of one asset's returns against another. "
            "Estimates alpha (intercept), beta (slope), and R-squared."
        ),
        "calculation": (
            "Fits Y = alpha + beta * X + epsilon using least squares. "
            "Alpha is the asset's excess return unexplained by the factor. "
            "Beta measures sensitivity to the factor. R-squared is the fraction of variance explained."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Dependent and independent asset prices", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "FactorModelsModule": {
        "title": "Factor Models",
        "description": (
            "Multi-factor regression analysis using academic factor models: "
            "CAPM, Fama-French 3/5, Carhart 4-Factor, Q-Factor (HXZ), and AQR factors."
        ),
        "calculation": (
            "Regresses excess asset returns on factor portfolios. CAPM uses market excess return. "
            "FF3 adds SMB (size) and HML (value). FF5 adds RMW (profitability) and CMA (investment). "
            "Alpha represents risk-adjusted abnormal return."
        ),
        "data_sources": [
            {"id": "Mkt-RF, SMB, HML, RMW, CMA, UMD", "name": "Fama-French factors from Ken French's library", "frequency": "Daily"},
            {"id": "R_MKT, R_ME, R_IA, R_ROE, R_EG", "name": "Q-Factors from global-q.org", "frequency": "Daily"},
            {"id": "BAB, QMJ, HML_DEVIL", "name": "AQR factors from AQR Data Library", "frequency": "Daily"},
        ],
        "source": "Fama-French / Q-Factor / AQR Data Libraries",
    },

    "MonthlyReturnsModule": {
        "title": "Monthly Returns Heatmap",
        "description": (
            "Calendar heatmap showing monthly returns for a portfolio or asset. "
            "Each cell is color-coded by return magnitude, with annual totals."
        ),
        "calculation": (
            "Monthly return = (end price / start price) - 1 for each calendar month. "
            "Annual return is the compounded product of monthly returns. "
            "Color scale ranges from red (negative) to green (positive)."
        ),
        "data_sources": [
            {"id": "User-defined tickers", "name": "Portfolio or asset prices", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "AssetClassReturnsModule": {
        "title": "Asset Class Returns",
        "description": (
            "Annual and cumulative return comparison across major asset classes "
            "including equities, bonds, commodities, REITs, and crypto."
        ),
        "calculation": (
            "Annual returns are calendar-year total returns for each ETF proxy. "
            "Cumulative returns show growth of $1 invested at the start of the period."
        ),
        "data_sources": [
            {"id": "SPY", "name": "Large Cap (S&P 500)", "frequency": "Daily"},
            {"id": "MDY", "name": "Mid Cap (S&P 400)", "frequency": "Daily"},
            {"id": "SPSM", "name": "Small Cap", "frequency": "Daily"},
            {"id": "EFA", "name": "International Stocks (EAFE)", "frequency": "Daily"},
            {"id": "EEM", "name": "Emerging Markets", "frequency": "Daily"},
            {"id": "VNQ", "name": "REITs", "frequency": "Daily"},
            {"id": "AGG", "name": "US Aggregate Bonds", "frequency": "Daily"},
            {"id": "TIP", "name": "TIPS (Inflation-Protected)", "frequency": "Daily"},
            {"id": "DJP", "name": "Commodities", "frequency": "Daily"},
            {"id": "BIL", "name": "Cash (T-Bills)", "frequency": "Daily"},
            {"id": "BTC-USD", "name": "Bitcoin", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    # ── Inflation ─────────────────────────────────────────────────────────────

    "CpiModule": {
        "title": "Consumer Price Index (CPI)",
        "description": (
            "Tracks changes in the average price level of a basket of consumer goods "
            "and services purchased by urban households. CPI is the most widely followed "
            "measure of consumer inflation in the United States."
        ),
        "calculation": (
            "Year-over-year percentage change in the CPI index relative to the same month "
            "one year prior. Core CPI excludes volatile food and energy components. "
            "Component breakdown shows weighted category contributions."
        ),
        "data_sources": [
            {"id": "CPIAUCSL", "name": "Headline CPI (All Urban Consumers)", "frequency": "Monthly"},
            {"id": "CPILFESL", "name": "Core CPI (Less Food & Energy)", "frequency": "Monthly"},
            {"id": "CPIFABSL", "name": "Food & Beverages", "frequency": "Monthly"},
            {"id": "CPIENGSL", "name": "Energy", "frequency": "Monthly"},
            {"id": "CPIHOSSL", "name": "Housing", "frequency": "Monthly"},
            {"id": "CPITRNSL", "name": "Transportation", "frequency": "Monthly"},
            {"id": "CPIMEDSL", "name": "Medical Care", "frequency": "Monthly"},
            {"id": "CPIAPPSL", "name": "Apparel", "frequency": "Monthly"},
            {"id": "CPIEDUSL", "name": "Education & Communication", "frequency": "Monthly"},
            {"id": "CPIRECSL", "name": "Recreation", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "PceModule": {
        "title": "Personal Consumption Expenditures (PCE)",
        "description": (
            "The Federal Reserve's preferred inflation gauge. PCE covers a broader range "
            "of expenditures than CPI and adjusts for substitution effects as consumers "
            "shift spending in response to price changes."
        ),
        "calculation": (
            "Year-over-year percentage change in the PCE price index. "
            "Core PCE excludes food and energy. The Fed targets 2% annual Core PCE inflation."
        ),
        "data_sources": [
            {"id": "PCEPI", "name": "PCE Price Index", "frequency": "Monthly"},
            {"id": "PCEPILFE", "name": "Core PCE (Less Food & Energy)", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "PpiModule": {
        "title": "Producer Price Index (PPI)",
        "description": (
            "Measures the average change in selling prices received by domestic producers. "
            "PPI is a leading indicator of consumer inflation since higher input costs "
            "are often passed to consumers."
        ),
        "calculation": (
            "Year-over-year percentage change in producer price indices. "
            "Core PPI excludes food and energy. PPI Final Demand covers goods and services "
            "sold for personal consumption, capital investment, government, and export."
        ),
        "data_sources": [
            {"id": "PPIFID", "name": "PPI Final Demand", "frequency": "Monthly"},
            {"id": "PPICOR", "name": "PPI Core (Less Food & Energy)", "frequency": "Monthly"},
            {"id": "PPIDES", "name": "PPI Energy", "frequency": "Monthly"},
            {"id": "PPIFDS", "name": "PPI Services", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "InflationExpectationsModule": {
        "title": "Inflation Expectations",
        "description": (
            "Market-based and survey-based measures of expected future inflation. "
            "Breakeven rates are derived from TIPS spreads; Michigan survey captures "
            "consumer expectations."
        ),
        "calculation": (
            "Breakeven inflation = nominal Treasury yield - TIPS yield of the same maturity. "
            "This represents the market's expectation of average annual CPI over that horizon. "
            "Michigan 1Y is the median expected price change over the next 12 months from the "
            "University of Michigan Survey of Consumers."
        ),
        "data_sources": [
            {"id": "T5YIEM", "name": "5-Year Breakeven Inflation Rate", "frequency": "Daily"},
            {"id": "T10YIEM", "name": "10-Year Breakeven Inflation Rate", "frequency": "Daily"},
            {"id": "MICH", "name": "Michigan 1-Year Inflation Expectations", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Treasury / Rates ──────────────────────────────────────────────────────

    "TreasuryModule": {
        "title": "Treasury Yields",
        "description": (
            "US Treasury yield curve from 1-month to 30-year maturities. "
            "Displays the current curve, historical curves, key spreads, and "
            "the 10Y-2Y spread as an indicator of economic expectations."
        ),
        "calculation": (
            "Yields are constant-maturity rates published by the US Treasury. "
            "The 10Y-2Y spread (slope of the curve) is the difference between "
            "10-year and 2-year yields. An inverted curve (negative spread) has "
            "historically preceded recessions."
        ),
        "data_sources": [
            {"id": "DGS1MO", "name": "1-Month Treasury", "frequency": "Daily"},
            {"id": "DGS3MO", "name": "3-Month Treasury", "frequency": "Daily"},
            {"id": "DGS6MO", "name": "6-Month Treasury", "frequency": "Daily"},
            {"id": "DGS1", "name": "1-Year Treasury", "frequency": "Daily"},
            {"id": "DGS2", "name": "2-Year Treasury", "frequency": "Daily"},
            {"id": "DGS3", "name": "3-Year Treasury", "frequency": "Daily"},
            {"id": "DGS5", "name": "5-Year Treasury", "frequency": "Daily"},
            {"id": "DGS7", "name": "7-Year Treasury", "frequency": "Daily"},
            {"id": "DGS10", "name": "10-Year Treasury", "frequency": "Daily"},
            {"id": "DGS20", "name": "20-Year Treasury", "frequency": "Daily"},
            {"id": "DGS30", "name": "30-Year Treasury", "frequency": "Daily"},
            {"id": "T10Y2Y", "name": "10Y-2Y Spread", "frequency": "Daily"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "RateProbabilityModule": {
        "title": "Fed Rate Probabilities",
        "description": (
            "Market-implied probabilities for future Federal Reserve interest rate decisions, "
            "derived from CME Fed Funds Futures. Shows the probability of each "
            "possible target rate at each upcoming FOMC meeting."
        ),
        "calculation": (
            "Implied fed funds rate = 100 - futures price. Probabilities are derived by "
            "comparing the implied rate to possible target rate outcomes. Uses a step-function "
            "model assuming the Fed moves in 25bp increments."
        ),
        "data_sources": [
            {"id": "DFEDTARU", "name": "Fed Funds Upper Target", "frequency": "Daily"},
            {"id": "DFEDTARL", "name": "Fed Funds Lower Target", "frequency": "Daily"},
            {"id": "ZQ*.CBT", "name": "CME Fed Funds Futures (18 months ahead)", "frequency": "Daily"},
        ],
        "source": "FRED + Yahoo Finance (CME Futures)",
    },

    # ── Labor Market ──────────────────────────────────────────────────────────

    "LaborMarketOverviewModule": {
        "title": "Unemployment Rate",
        "description": (
            "The official U-3 unemployment rate and the broader U-6 measure which "
            "includes discouraged workers and those marginally attached to the labor force."
        ),
        "calculation": (
            "U-3 = (unemployed / civilian labor force) x 100. "
            "U-6 adds marginally attached workers, discouraged workers, and those "
            "employed part-time for economic reasons."
        ),
        "data_sources": [
            {"id": "UNRATE", "name": "U-3 Unemployment Rate", "frequency": "Monthly"},
            {"id": "U6RATE", "name": "U-6 Unemployment Rate", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "DemographicsModule": {
        "title": "Unemployment Demographics",
        "description": (
            "Unemployment rates broken down by race, gender, and age group. "
            "Reveals disparities in labor market conditions across demographic segments."
        ),
        "calculation": (
            "Each rate = (unemployed in group / civilian labor force in group) x 100. "
            "Based on the Current Population Survey (CPS) household survey."
        ),
        "data_sources": [
            {"id": "LNS14000003", "name": "White Unemployment Rate", "frequency": "Monthly"},
            {"id": "LNS14000006", "name": "Black Unemployment Rate", "frequency": "Monthly"},
            {"id": "LNS14000009", "name": "Hispanic Unemployment Rate", "frequency": "Monthly"},
            {"id": "LNS14000024", "name": "Men 20+ Unemployment Rate", "frequency": "Monthly"},
            {"id": "LNS14000025", "name": "Women 20+ Unemployment Rate", "frequency": "Monthly"},
            {"id": "LNU04000012", "name": "Youth (16-24) Unemployment Rate", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "PayrollsModule": {
        "title": "Nonfarm Payrolls",
        "description": (
            "Monthly change in total nonfarm employment, the headline jobs number. "
            "Sector breakdown shows which industries are driving job creation or losses."
        ),
        "calculation": (
            "Month-over-month change in seasonally adjusted nonfarm payroll employment. "
            "Based on the Current Employment Statistics (CES) establishment survey, "
            "covering ~145,000 businesses and government agencies."
        ),
        "data_sources": [
            {"id": "PAYEMS", "name": "Total Nonfarm Payrolls", "frequency": "Monthly"},
            {"id": "USCONS", "name": "Construction", "frequency": "Monthly"},
            {"id": "MANEMP", "name": "Manufacturing", "frequency": "Monthly"},
            {"id": "USFIRE", "name": "Financial Activities", "frequency": "Monthly"},
            {"id": "USPBS", "name": "Professional & Business Services", "frequency": "Monthly"},
            {"id": "USEHS", "name": "Education & Health Services", "frequency": "Monthly"},
            {"id": "USLAH", "name": "Leisure & Hospitality", "frequency": "Monthly"},
            {"id": "USINFO", "name": "Information", "frequency": "Monthly"},
            {"id": "USGOVT", "name": "Government", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "LaborClaimsModule": {
        "title": "Unemployment Claims",
        "description": (
            "Weekly initial and continued unemployment insurance claims. "
            "Initial claims are a leading indicator of labor market deterioration; "
            "rising claims signal increasing layoffs."
        ),
        "calculation": (
            "Initial claims = new filings for unemployment benefits in the reporting week. "
            "Continued claims = total individuals receiving unemployment benefits. "
            "4-week moving average smooths weekly volatility."
        ),
        "data_sources": [
            {"id": "ICSA", "name": "Initial Claims (Weekly)", "frequency": "Weekly"},
            {"id": "CCSA", "name": "Continued Claims (Weekly)", "frequency": "Weekly"},
            {"id": "IC4WSA", "name": "Initial Claims 4-Week Moving Average", "frequency": "Weekly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "JoltsModule": {
        "title": "JOLTS (Job Openings & Labor Turnover)",
        "description": (
            "Bureau of Labor Statistics survey tracking job openings, hires, quits, "
            "and layoffs. The quits rate is considered a barometer of worker confidence."
        ),
        "calculation": (
            "Levels in thousands. Quits rate = (quits / total employment) x 100. "
            "A rising quits rate indicates workers are confident about finding better jobs."
        ),
        "data_sources": [
            {"id": "JTSJOL", "name": "Job Openings", "frequency": "Monthly"},
            {"id": "JTSHIL", "name": "Hires", "frequency": "Monthly"},
            {"id": "JTSQUL", "name": "Quits", "frequency": "Monthly"},
            {"id": "JTSLDR", "name": "Layoffs & Discharges", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Monetary Policy ───────────────────────────────────────────────────────

    "MoneySupplyModule": {
        "title": "Money Supply (M1 & M2)",
        "description": (
            "Broad measures of the US money stock. M1 includes the most liquid forms "
            "(currency, demand deposits). M2 adds savings deposits, money market funds, "
            "and small time deposits."
        ),
        "calculation": (
            "Levels in billions of dollars, seasonally adjusted. "
            "Year-over-year growth rate shows the pace of monetary expansion or contraction."
        ),
        "data_sources": [
            {"id": "M1SL", "name": "M1 Money Stock", "frequency": "Monthly"},
            {"id": "M2SL", "name": "M2 Money Stock", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "FedBalanceSheetModule": {
        "title": "Federal Reserve Balance Sheet",
        "description": (
            "Total assets held by the Federal Reserve, broken down by type. "
            "QE (quantitative easing) expands the balance sheet; QT (quantitative tightening) "
            "shrinks it. A key indicator of monetary policy stance."
        ),
        "calculation": (
            "Total assets in millions of dollars, reported weekly. "
            "Components include Treasury securities, mortgage-backed securities (MBS), "
            "agency debt, and loans to financial institutions."
        ),
        "data_sources": [
            {"id": "WALCL", "name": "Total Assets", "frequency": "Weekly"},
            {"id": "WSHOTSL", "name": "Treasury Securities Held", "frequency": "Weekly"},
            {"id": "WSHOMCB", "name": "Mortgage-Backed Securities (MBS)", "frequency": "Weekly"},
            {"id": "WSHOFADSL", "name": "Federal Agency Debt Securities", "frequency": "Weekly"},
            {"id": "WLCFLL", "name": "Loans", "frequency": "Weekly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "FedFundsRateModule": {
        "title": "Federal Funds Rate",
        "description": (
            "The interest rate at which banks lend reserve balances to each other overnight. "
            "The Fed's primary tool for implementing monetary policy. "
            "Shows the effective rate and the target range."
        ),
        "calculation": (
            "The effective federal funds rate (EFFR) is the volume-weighted median rate "
            "of overnight federal funds transactions. The target range is set by the FOMC."
        ),
        "data_sources": [
            {"id": "FEDFUNDS", "name": "Effective Federal Funds Rate", "frequency": "Monthly"},
            {"id": "DFEDTARL", "name": "Target Range Lower Bound", "frequency": "Daily"},
            {"id": "DFEDTARU", "name": "Target Range Upper Bound", "frequency": "Daily"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "ReserveBalancesModule": {
        "title": "Reserve Balances",
        "description": (
            "Deposits held by depository institutions at Federal Reserve Banks. "
            "Reserve balances are a key indicator of banking system liquidity "
            "and the effectiveness of QE/QT."
        ),
        "calculation": (
            "Total reserve balances in millions of dollars, reported weekly. "
            "During QE, reserves expand as the Fed purchases securities. "
            "During QT, reserves contract as securities mature without reinvestment."
        ),
        "data_sources": [
            {"id": "WRBWFRBL", "name": "Reserve Balances with Federal Reserve Banks", "frequency": "Weekly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "MoneyVelocityModule": {
        "title": "Velocity of Money (M2)",
        "description": (
            "The rate at which money circulates through the economy. "
            "Falling velocity means each dollar generates less economic activity, "
            "offsetting the effect of money supply growth."
        ),
        "calculation": (
            "M2 Velocity = Nominal GDP / M2 Money Stock. "
            "A declining trend suggests increasing money hoarding or financial asset accumulation. "
            "Reported quarterly since it depends on GDP data."
        ),
        "data_sources": [
            {"id": "M2V", "name": "Velocity of M2 Money Stock", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── GDP & Output ──────────────────────────────────────────────────────────

    "GdpModule": {
        "title": "Gross Domestic Product (GDP)",
        "description": (
            "The total value of all goods and services produced in the US. "
            "Displays real (inflation-adjusted) and nominal GDP with a stacked "
            "component breakdown: consumption, investment, government, and net exports."
        ),
        "calculation": (
            "GDP = C + I + G + (X - M). Real GDP uses chained 2017 dollars. "
            "Year-over-year growth rate shows the pace of economic expansion. "
            "Annualized quarterly growth is the BEA's standard reporting format."
        ),
        "data_sources": [
            {"id": "GDPC1", "name": "Real GDP", "frequency": "Quarterly"},
            {"id": "GDP", "name": "Nominal GDP", "frequency": "Quarterly"},
            {"id": "A191RL1Q225SBEA", "name": "Real GDP Growth Rate (Annualized)", "frequency": "Quarterly"},
            {"id": "PCECC96", "name": "Real Personal Consumption Expenditures", "frequency": "Quarterly"},
            {"id": "GPDIC1", "name": "Real Gross Private Domestic Investment", "frequency": "Quarterly"},
            {"id": "GCEC1", "name": "Real Government Consumption & Investment", "frequency": "Quarterly"},
            {"id": "EXPGSC1", "name": "Real Exports", "frequency": "Quarterly"},
            {"id": "IMPGSC1", "name": "Real Imports", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "IndustrialProductionModule": {
        "title": "Industrial Production & Capacity Utilization",
        "description": (
            "Measures real output of the manufacturing, mining, and utility sectors. "
            "Capacity utilization shows the percentage of productive capacity in use."
        ),
        "calculation": (
            "Industrial Production Index is a chain-weighted index (2017 = 100). "
            "Capacity utilization = (actual output / potential output) x 100. "
            "Year-over-year changes show the growth trajectory."
        ),
        "data_sources": [
            {"id": "INDPRO", "name": "Industrial Production Index", "frequency": "Monthly"},
            {"id": "IPMAN", "name": "Manufacturing Production", "frequency": "Monthly"},
            {"id": "TCU", "name": "Total Capacity Utilization", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "ConsumerSentimentModule": {
        "title": "Consumer Sentiment",
        "description": (
            "The University of Michigan Index of Consumer Sentiment, a survey-based "
            "measure of consumer confidence in current and future economic conditions."
        ),
        "calculation": (
            "Index based on five survey questions covering personal finances and "
            "business conditions. Baseline of 100 set in 1966. Values above 100 "
            "indicate above-average optimism."
        ),
        "data_sources": [
            {"id": "UMCSENT", "name": "University of Michigan Consumer Sentiment Index", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Housing ───────────────────────────────────────────────────────────────

    "HousingStartsModule": {
        "title": "Housing Starts",
        "description": (
            "New residential construction starts, a leading indicator of housing "
            "market activity and broader economic health. Includes single-family "
            "and multi-unit structures."
        ),
        "calculation": (
            "Seasonally adjusted annual rate (SAAR) in thousands of units. "
            "Single-family starts reflect homebuilder confidence. "
            "Multi-unit (5+ units) starts reflect apartment/rental demand."
        ),
        "data_sources": [
            {"id": "HOUST", "name": "Total Housing Starts", "frequency": "Monthly"},
            {"id": "HOUST1F", "name": "Single-Family Starts", "frequency": "Monthly"},
            {"id": "HOUST5F", "name": "5+ Unit Starts", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "HousingPermitsModule": {
        "title": "Building Permits",
        "description": (
            "Authorized new residential construction permits. Permits lead starts "
            "by 1-2 months, making them an earlier indicator of housing activity."
        ),
        "calculation": (
            "Seasonally adjusted annual rate (SAAR) in thousands of units. "
            "A permit authorizes construction but doesn't guarantee a start."
        ),
        "data_sources": [
            {"id": "PERMIT", "name": "Total Building Permits", "frequency": "Monthly"},
            {"id": "PERMIT1", "name": "Single-Family Permits", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "HomePricesModule": {
        "title": "Home Prices",
        "description": (
            "Major US home price indices tracking the trajectory of residential "
            "real estate values. Includes repeat-sale indices and median/average "
            "transaction prices."
        ),
        "calculation": (
            "Case-Shiller uses repeat-sale methodology comparing the price of the "
            "same property across transactions. Median and average sale prices are "
            "from the Census Bureau's survey of new and existing home sales."
        ),
        "data_sources": [
            {"id": "CSUSHPINSA", "name": "Case-Shiller US National Home Price Index", "frequency": "Monthly"},
            {"id": "SPCS20RSA", "name": "Case-Shiller 20-City Composite", "frequency": "Monthly"},
            {"id": "MSPUS", "name": "Median Sales Price of Houses Sold", "frequency": "Quarterly"},
            {"id": "ASPUS", "name": "Average Sales Price of Houses Sold", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "HomeSalesModule": {
        "title": "Home Sales",
        "description": (
            "Existing and new home sales volumes. Sales pace is a key indicator "
            "of housing demand and overall market activity."
        ),
        "calculation": (
            "Existing home sales are reported as a seasonally adjusted annual rate (SAAR) "
            "in millions. New home sales in thousands. Both measure completed transactions."
        ),
        "data_sources": [
            {"id": "EXHOSLUSM495S", "name": "Existing Home Sales", "frequency": "Monthly"},
            {"id": "HSN1F", "name": "New One-Family Houses Sold", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "HousingSupplyModule": {
        "title": "Housing Supply",
        "description": (
            "Months of supply for new and existing homes, plus the homeownership rate. "
            "Supply is a key indicator of market tightness; below 4 months is a seller's market."
        ),
        "calculation": (
            "Months supply = inventory / monthly sales pace. "
            "Homeownership rate = (owner-occupied units / total occupied units) x 100."
        ),
        "data_sources": [
            {"id": "MNMFS", "name": "New Homes Months Supply", "frequency": "Monthly"},
            {"id": "MSACSR", "name": "Existing Homes Months Supply", "frequency": "Monthly"},
            {"id": "RHORUSQ156N", "name": "Homeownership Rate", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "CommercialRealEstateModule": {
        "title": "Commercial Real Estate",
        "description": (
            "Commercial real estate price index tracking the value of commercial "
            "properties (office, retail, industrial, multifamily)."
        ),
        "calculation": (
            "Index level based on commercial property transactions. "
            "Year-over-year percentage change shows the direction and pace of "
            "commercial property value appreciation or decline."
        ),
        "data_sources": [
            {"id": "COMREPUSQ159N", "name": "Commercial Real Estate Price Index", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Consumer & Retail ─────────────────────────────────────────────────────

    "RetailSalesModule": {
        "title": "Retail Sales",
        "description": (
            "Total and real (inflation-adjusted) retail and food services sales. "
            "Consumer spending drives ~70% of GDP, making retail sales a key "
            "coincident indicator of economic activity."
        ),
        "calculation": (
            "Advance Monthly Retail Trade Survey from the Census Bureau. "
            "Nominal sales in millions of dollars. Real retail sales deflated by CPI. "
            "Year-over-year changes show the spending trend."
        ),
        "data_sources": [
            {"id": "RSAFS", "name": "Retail Sales (Nominal)", "frequency": "Monthly"},
            {"id": "RRSFS", "name": "Real Retail Sales (Inflation-Adjusted)", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "VehicleSalesModule": {
        "title": "Vehicle Sales",
        "description": (
            "Total motor vehicle sales including light autos and heavy trucks. "
            "Auto sales are a major consumer durables indicator and a bellwether "
            "for consumer credit conditions."
        ),
        "calculation": (
            "Seasonally adjusted annual rate (SAAR) in millions of units. "
            "Light vehicles include passenger cars and light trucks. "
            "Heavy trucks are a proxy for commercial/freight activity."
        ),
        "data_sources": [
            {"id": "TOTALSA", "name": "Total Vehicle Sales", "frequency": "Monthly"},
            {"id": "LAUTOSA", "name": "Light Auto Sales", "frequency": "Monthly"},
            {"id": "HTRUCKSSA", "name": "Heavy Truck Sales", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "MortgageRatesModule": {
        "title": "Mortgage Rates",
        "description": (
            "Average weekly mortgage rates for 30-year and 15-year fixed-rate "
            "conforming mortgages, reported by Freddie Mac's Primary Mortgage Market Survey."
        ),
        "calculation": (
            "Rates are national averages for purchase originations with 80% LTV. "
            "The 30-year rate is the most commonly cited mortgage benchmark."
        ),
        "data_sources": [
            {"id": "MORTGAGE30US", "name": "30-Year Fixed Mortgage Rate", "frequency": "Weekly"},
            {"id": "MORTGAGE15US", "name": "15-Year Fixed Mortgage Rate", "frequency": "Weekly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "DurableGoodsModule": {
        "title": "Durable Goods Orders",
        "description": (
            "New orders for manufactured durable goods (items expected to last 3+ years). "
            "A leading indicator of manufacturing activity and business investment."
        ),
        "calculation": (
            "Millions of dollars, seasonally adjusted. Core capital goods orders "
            "(nondefense, excluding aircraft) is the best proxy for business equipment spending."
        ),
        "data_sources": [
            {"id": "DGORDER", "name": "Total Durable Goods Orders", "frequency": "Monthly"},
            {"id": "NEWORDER", "name": "Core Capital Goods Orders (Nondefense ex Aircraft)", "frequency": "Monthly"},
            {"id": "AMDMUO", "name": "Unfilled Durable Goods Orders", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Financial Conditions ──────────────────────────────────────────────────

    "FinancialConditionsModule": {
        "title": "Financial Conditions Index",
        "description": (
            "Chicago Fed National Financial Conditions Index (NFCI) and sub-indices. "
            "Measures the degree of financial stress in money, debt, and equity markets."
        ),
        "calculation": (
            "NFCI is a weighted average of 105 indicators of financial activity. "
            "Positive values indicate tighter-than-average conditions. "
            "Sub-indices isolate credit, leverage, and non-financial leverage components."
        ),
        "data_sources": [
            {"id": "NFCI", "name": "National Financial Conditions Index", "frequency": "Weekly"},
            {"id": "ANFCI", "name": "Adjusted NFCI (removes business cycle effects)", "frequency": "Weekly"},
            {"id": "NFCICREDIT", "name": "Credit Sub-Index", "frequency": "Weekly"},
            {"id": "NFCILEVERAGE", "name": "Leverage Sub-Index", "frequency": "Weekly"},
            {"id": "NFCINONFINLEVERAGE", "name": "Non-Financial Leverage Sub-Index", "frequency": "Weekly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "CorporateSpreadsModule": {
        "title": "Corporate Bond Spreads",
        "description": (
            "Credit spreads between corporate bonds and Treasury yields. "
            "Widening spreads indicate rising credit risk and deteriorating financial conditions."
        ),
        "calculation": (
            "Spread = corporate bond yield - Treasury yield of comparable maturity. "
            "Baa-10Y and Aaa-10Y use Moody's corporate bond indices. "
            "HY OAS is the option-adjusted spread for the BofA High Yield index."
        ),
        "data_sources": [
            {"id": "BAA10Y", "name": "Moody's Baa - 10Y Treasury Spread", "frequency": "Daily"},
            {"id": "AAA10Y", "name": "Moody's Aaa - 10Y Treasury Spread", "frequency": "Daily"},
            {"id": "BAMLH0A0HYM2", "name": "ICE BofA High Yield OAS", "frequency": "Daily"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "FinancialStressModule": {
        "title": "Financial Stress Indices",
        "description": (
            "Composite stress indices from the St. Louis Fed and Kansas City Fed. "
            "Measure overall strain in financial markets including credit, equity, "
            "and funding markets."
        ),
        "calculation": (
            "STLFSI4: Weekly index based on 18 data series; zero = normal conditions, "
            "positive = above-average stress. KCFSI: Monthly index based on 11 variables "
            "capturing credit, equity, and funding market stress."
        ),
        "data_sources": [
            {"id": "STLFSI4", "name": "St. Louis Fed Financial Stress Index", "frequency": "Weekly"},
            {"id": "KCFSI", "name": "Kansas City Fed Financial Stress Index", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "VolatilityModule": {
        "title": "Volatility Indices",
        "description": (
            "Implied volatility measures across major asset classes. "
            "The VIX ('Fear Index') measures expected S&P 500 volatility from options pricing. "
            "MOVE measures Treasury bond volatility."
        ),
        "calculation": (
            "VIX is calculated from S&P 500 option prices and represents the market's "
            "expectation of 30-day annualized volatility. A VIX above 20 generally indicates "
            "elevated fear; above 30 suggests market panic."
        ),
        "data_sources": [
            {"id": "VIXCLS", "name": "CBOE VIX (S&P 500 Volatility)", "frequency": "Daily"},
            {"id": "VXVCLS", "name": "3-Month VIX", "frequency": "Daily"},
            {"id": "OVXCLS", "name": "Oil Volatility (OVX)", "frequency": "Daily"},
            {"id": "VXNCLS", "name": "NASDAQ Volatility (VXN)", "frequency": "Daily"},
            {"id": "RVXCLS", "name": "Russell 2000 Volatility (RVX)", "frequency": "Daily"},
            {"id": "VXDCLS", "name": "DJIA Volatility (VXD)", "frequency": "Daily"},
            {"id": "VXEEMCLS", "name": "Emerging Markets Volatility (VXEEM)", "frequency": "Daily"},
            {"id": "^MOVE", "name": "MOVE Index (Treasury Bond Volatility)", "frequency": "Daily"},
        ],
        "source": "FRED + Yahoo Finance",
    },

    # ── Trade & Fiscal ────────────────────────────────────────────────────────

    "TradeBalanceModule": {
        "title": "Trade Balance",
        "description": (
            "US balance of trade in goods and services. Shows total exports, imports, "
            "and the net trade balance. A persistent deficit means the US imports "
            "more than it exports."
        ),
        "calculation": (
            "Trade balance = exports - imports. Reported in millions of dollars, "
            "seasonally adjusted. Census basis for goods, BEA basis for services."
        ),
        "data_sources": [
            {"id": "BOPGSTB", "name": "Trade Balance (Goods & Services)", "frequency": "Monthly"},
            {"id": "BOPTEXP", "name": "Total Exports", "frequency": "Monthly"},
            {"id": "BOPTIMP", "name": "Total Imports", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "GovernmentDebtModule": {
        "title": "Government Debt",
        "description": (
            "Total US public debt outstanding and the debt-to-GDP ratio. "
            "Tracks the federal government's total borrowing over time."
        ),
        "calculation": (
            "Total debt in millions of dollars. Debt-to-GDP ratio = "
            "(total public debt / nominal GDP) x 100. Includes debt held by "
            "the public and intragovernmental holdings."
        ),
        "data_sources": [
            {"id": "GFDEBTN", "name": "Federal Debt: Total Public Debt", "frequency": "Quarterly"},
            {"id": "GFDEGDQ188S", "name": "Federal Debt to GDP Ratio", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Credit ────────────────────────────────────────────────────────────────

    "DelinquencyRatesModule": {
        "title": "Delinquency Rates",
        "description": (
            "Percentage of loans past due at commercial banks. Rising delinquency "
            "rates signal deteriorating borrower health and potential credit losses."
        ),
        "calculation": (
            "Delinquency rate = (value of loans past due / total value of loans) x 100. "
            "Reported quarterly by the Federal Reserve's charge-off and delinquency data."
        ),
        "data_sources": [
            {"id": "DRCCLACBS", "name": "Credit Card Delinquency Rate", "frequency": "Quarterly"},
            {"id": "DRALACBS", "name": "All Loans Delinquency Rate", "frequency": "Quarterly"},
            {"id": "DRCLACBS", "name": "Consumer Loans Delinquency Rate", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "ConsumerCreditModule": {
        "title": "Consumer Credit",
        "description": (
            "Total consumer credit outstanding broken into revolving (credit cards) "
            "and non-revolving (auto loans, student loans) components."
        ),
        "calculation": (
            "Outstanding balances in billions of dollars, seasonally adjusted. "
            "Revolving credit fluctuates with consumer spending. "
            "Non-revolving credit grows more steadily with auto and education lending."
        ),
        "data_sources": [
            {"id": "TOTALSL", "name": "Total Consumer Credit Outstanding", "frequency": "Monthly"},
            {"id": "REVOLSL", "name": "Revolving Consumer Credit", "frequency": "Monthly"},
            {"id": "NONREVSL", "name": "Non-Revolving Consumer Credit", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Commodities ───────────────────────────────────────────────────────────

    "MetalsModule": {
        "title": "Precious & Industrial Metals",
        "description": (
            "Futures prices for gold, silver, copper, platinum, and palladium. "
            "Gold and silver are safe-haven assets; copper is a barometer of "
            "industrial activity ('Dr. Copper')."
        ),
        "calculation": (
            "Normalized view: all prices rebased to 100 at the start of the lookback period "
            "for relative performance comparison. Raw view: actual futures prices in USD."
        ),
        "data_sources": [
            {"id": "GC=F", "name": "Gold Futures", "frequency": "Daily"},
            {"id": "SI=F", "name": "Silver Futures", "frequency": "Daily"},
            {"id": "HG=F", "name": "Copper Futures", "frequency": "Daily"},
            {"id": "PL=F", "name": "Platinum Futures", "frequency": "Daily"},
            {"id": "PA=F", "name": "Palladium Futures", "frequency": "Daily"},
        ],
        "source": "Yahoo Finance",
    },

    "CrudeOilModule": {
        "title": "Crude Oil",
        "description": (
            "WTI and Brent crude oil benchmark prices. WTI is the US benchmark; "
            "Brent is the international benchmark. Key inputs to energy costs, "
            "inflation, and geopolitical risk."
        ),
        "calculation": (
            "Spot prices in dollars per barrel. "
            "Year-over-year change shows the inflationary or deflationary impulse from energy."
        ),
        "data_sources": [
            {"id": "DCOILWTICO", "name": "WTI Crude Oil Price", "frequency": "Daily"},
            {"id": "DCOILBRENTEU", "name": "Brent Crude Oil Price", "frequency": "Daily"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "NaturalGasModule": {
        "title": "Natural Gas",
        "description": (
            "Henry Hub natural gas spot price, the primary US pricing benchmark. "
            "Natural gas is a key input for electricity generation, heating, "
            "and industrial processes."
        ),
        "calculation": (
            "Price in dollars per million BTU at the Henry Hub delivery point in Louisiana."
        ),
        "data_sources": [
            {"id": "DHHNGSP", "name": "Henry Hub Natural Gas Spot Price", "frequency": "Daily"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Income & Wealth ───────────────────────────────────────────────────────

    "PersonalIncomeModule": {
        "title": "Personal Income",
        "description": (
            "Aggregate personal income and disposable personal income for the US. "
            "Shows both nominal and real (inflation-adjusted) measures."
        ),
        "calculation": (
            "Personal income = wages + proprietors' income + rental income + dividends "
            "+ interest + transfer payments. Disposable income = personal income - personal taxes."
        ),
        "data_sources": [
            {"id": "PI", "name": "Personal Income", "frequency": "Monthly"},
            {"id": "DSPI", "name": "Disposable Personal Income", "frequency": "Monthly"},
            {"id": "RPI", "name": "Real Personal Income", "frequency": "Monthly"},
            {"id": "DSPIC96", "name": "Real Disposable Personal Income", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "SavingsRateModule": {
        "title": "Personal Savings Rate",
        "description": (
            "The percentage of disposable income that households save rather than spend. "
            "A low savings rate suggests consumers are stretching budgets; "
            "a high rate may indicate caution about the economic outlook."
        ),
        "calculation": (
            "Savings rate = (disposable personal income - personal outlays) "
            "/ disposable personal income x 100."
        ),
        "data_sources": [
            {"id": "PSAVERT", "name": "Personal Savings Rate", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "WageGrowthModule": {
        "title": "Wage Growth",
        "description": (
            "Measures of worker compensation growth including average hourly earnings "
            "and the Employment Cost Index (ECI). Key for assessing labor cost pressures "
            "and real purchasing power."
        ),
        "calculation": (
            "Average Hourly Earnings: mean hourly pay for all private nonfarm employees. "
            "ECI Wages: quarterly index of employer labor costs (wages only, excludes benefits). "
            "Year-over-year growth rates show the wage inflation trend."
        ),
        "data_sources": [
            {"id": "CES0500000003", "name": "Average Hourly Earnings (All Private)", "frequency": "Monthly"},
            {"id": "ECIWAG", "name": "Employment Cost Index: Wages & Salaries", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "HouseholdWealthModule": {
        "title": "Household Net Worth",
        "description": (
            "Total household net worth and debt service ratios. "
            "Net worth = total assets - total liabilities for all US households."
        ),
        "calculation": (
            "Reported in billions of dollars from the Financial Accounts of the United States "
            "(Z.1 Flow of Funds). Debt service ratio = required debt payments / disposable income."
        ),
        "data_sources": [
            {"id": "BOGZ1FL192090005Q", "name": "Household Net Worth", "frequency": "Quarterly"},
            {"id": "TDSP", "name": "Household Debt Service Ratio", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "HouseholdDebtModule": {
        "title": "Household Debt",
        "description": (
            "Total household debt outstanding and the household debt-to-GDP ratio. "
            "Tracks consumer leverage and deleveraging cycles."
        ),
        "calculation": (
            "Household debt in billions of dollars. "
            "Debt-to-GDP ratio = household debt / nominal GDP x 100."
        ),
        "data_sources": [
            {"id": "CMDEBT", "name": "Household Debt Outstanding", "frequency": "Quarterly"},
            {"id": "HDTGPDUSQ163N", "name": "Household Debt to GDP Ratio", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "WealthDistributionModule": {
        "title": "Wealth Distribution",
        "description": (
            "Distribution of household wealth by percentile group. "
            "Shows the share of total net worth held by the top 1%, "
            "90th-99th percentile, 50th-90th, and bottom 50%."
        ),
        "calculation": (
            "Wealth shares from the Distributional Financial Accounts (DFA). "
            "Each series represents the percentage of total household net worth "
            "held by that wealth percentile group."
        ),
        "data_sources": [
            {"id": "WFRBST01134", "name": "Top 1% Net Worth Share", "frequency": "Quarterly"},
            {"id": "WFRBSN09161", "name": "90th-99th Percentile Share", "frequency": "Quarterly"},
            {"id": "WFRBSN40188", "name": "50th-90th Percentile Share", "frequency": "Quarterly"},
            {"id": "WFRBSB50215", "name": "Bottom 50% Share", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "IncomeInequalityModule": {
        "title": "Income Inequality",
        "description": (
            "Median household and personal income levels. "
            "Tracks the income trajectory for the typical American household."
        ),
        "calculation": (
            "Median = the middle value in the income distribution. "
            "Reported annually from the Census Bureau's Current Population Survey. "
            "Nominal dollars (not inflation-adjusted)."
        ),
        "data_sources": [
            {"id": "MEHOINUSA672N", "name": "Median Household Income", "frequency": "Annual"},
            {"id": "MEPAINUSA672N", "name": "Median Personal Income", "frequency": "Annual"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Banking & Lending ─────────────────────────────────────────────────────

    "BankLendingModule": {
        "title": "Bank Lending",
        "description": (
            "Total loans and leases at commercial banks, broken down by type. "
            "Credit growth supports economic expansion; contraction signals tightening."
        ),
        "calculation": (
            "Outstanding loan balances in billions of dollars, seasonally adjusted. "
            "Year-over-year growth rates show the pace of credit creation."
        ),
        "data_sources": [
            {"id": "TOTLL", "name": "Total Loans & Leases", "frequency": "Weekly"},
            {"id": "BUSLOANS", "name": "Commercial & Industrial Loans", "frequency": "Weekly"},
            {"id": "REALLN", "name": "Real Estate Loans", "frequency": "Weekly"},
            {"id": "CONSUMER", "name": "Consumer Loans", "frequency": "Weekly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "LoanSurveyModule": {
        "title": "Senior Loan Officer Survey (SLOOS)",
        "description": (
            "Federal Reserve survey of bank lending standards and demand. "
            "Tightening standards restrict credit availability; easing standards "
            "signal banks are more willing to lend."
        ),
        "calculation": (
            "Net percentage of banks tightening standards = (% tightening - % easing). "
            "Positive values = net tightening, negative = net easing. "
            "Conducted quarterly among ~80 large domestic banks."
        ),
        "data_sources": [
            {"id": "DRTSCILM", "name": "C&I Loans to Large Firms (Tightening)", "frequency": "Quarterly"},
            {"id": "DRTSCIS", "name": "C&I Loans to Small Firms (Tightening)", "frequency": "Quarterly"},
            {"id": "DRTSCLCC", "name": "Credit Card Loans (Tightening)", "frequency": "Quarterly"},
            {"id": "SUBLPDHMSENQ", "name": "Mortgage Loans (Tightening)", "frequency": "Quarterly"},
            {"id": "STDSAUTO", "name": "Auto Loans (Tightening)", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "StudentLoansModule": {
        "title": "Student Loans",
        "description": (
            "Outstanding student loan debt in the United States. "
            "Student debt is the second-largest consumer debt category after mortgages."
        ),
        "calculation": (
            "Outstanding balances in billions of dollars from the Financial Accounts "
            "and the Federal Reserve's consumer credit data."
        ),
        "data_sources": [
            {"id": "SLOAS", "name": "Total Student Loans Outstanding", "frequency": "Quarterly"},
            {"id": "FGCCSAQ027S", "name": "Federal Government Student Loans", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    # ── Miscellaneous ─────────────────────────────────────────────────────────

    "ProductivityModule": {
        "title": "Productivity",
        "description": (
            "Labor productivity, unit labor costs, and real compensation in the "
            "nonfarm business sector. Productivity growth is the primary driver "
            "of long-run living standards."
        ),
        "calculation": (
            "Productivity = real output / hours worked. "
            "Unit labor costs = compensation / real output (rising ULC squeezes margins). "
            "Real compensation = nominal compensation adjusted for inflation."
        ),
        "data_sources": [
            {"id": "OPHNFB", "name": "Nonfarm Business Productivity (Output per Hour)", "frequency": "Quarterly"},
            {"id": "ULCNFB", "name": "Nonfarm Business Unit Labor Costs", "frequency": "Quarterly"},
            {"id": "COMPRNFB", "name": "Nonfarm Business Real Compensation per Hour", "frequency": "Quarterly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "CurrencyModule": {
        "title": "Currency & Dollar Index",
        "description": (
            "Trade-weighted US Dollar Index and major currency pairs. "
            "A strong dollar makes US exports more expensive and imports cheaper."
        ),
        "calculation": (
            "Dollar Index is a trade-weighted geometric average of USD exchange rates "
            "against major trading partners. Individual pairs show bilateral exchange rates."
        ),
        "data_sources": [
            {"id": "DTWEXBGS", "name": "Trade-Weighted Dollar Index (Broad)", "frequency": "Daily"},
            {"id": "DTWEXAFEGS", "name": "Dollar Index (Advanced Economies)", "frequency": "Daily"},
            {"id": "DEXUSEU", "name": "EUR/USD Exchange Rate", "frequency": "Daily"},
            {"id": "DEXJPUS", "name": "USD/JPY Exchange Rate", "frequency": "Daily"},
            {"id": "DEXCHUS", "name": "USD/CNY Exchange Rate", "frequency": "Daily"},
            {"id": "DEXUSUK", "name": "GBP/USD Exchange Rate", "frequency": "Daily"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "SahmRuleModule": {
        "title": "Sahm Rule Recession Indicator",
        "description": (
            "Real-time recession indicator developed by economist Claudia Sahm. "
            "Triggers when the 3-month moving average of the unemployment rate "
            "rises 0.50 percentage points or more above its prior 12-month low."
        ),
        "calculation": (
            "Sahm Rule = current 3-month avg unemployment rate - lowest 3-month avg "
            "over the prior 12 months. Values at or above 0.50 have historically "
            "coincided with the onset of a recession."
        ),
        "data_sources": [
            {"id": "SAHMCURRENT", "name": "Sahm Rule Recession Indicator", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "RecessionProbabilityModule": {
        "title": "Recession Probability",
        "description": (
            "Model-estimated probability that the US economy is in a recession, "
            "plus the Chicago Fed National Activity Index (CFNAI). "
            "The probability model uses the yield curve slope and other predictors."
        ),
        "calculation": (
            "Recession probability is a smoothed Markov-switching model output (0-100%). "
            "CFNAI is a weighted average of 85 monthly indicators; values below -0.70 "
            "after a period of expansion suggest a recession has begun."
        ),
        "data_sources": [
            {"id": "RECPROUSM156N", "name": "Smoothed US Recession Probability", "frequency": "Monthly"},
            {"id": "CFNAI", "name": "Chicago Fed National Activity Index", "frequency": "Monthly"},
            {"id": "CFNAIMA3", "name": "CFNAI 3-Month Moving Average", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "PopulationModule": {
        "title": "Population",
        "description": (
            "US total population, working-age population, and civilian "
            "noninstitutional population. Demographic trends drive long-run "
            "labor supply and economic growth potential."
        ),
        "calculation": (
            "Population levels in thousands. Working age is defined as 15-64 years. "
            "Civilian noninstitutional population (16+) is the base for labor force statistics."
        ),
        "data_sources": [
            {"id": "POPTHM", "name": "Total US Population", "frequency": "Monthly"},
            {"id": "LFWA64TTUSM647S", "name": "Working Age Population (15-64)", "frequency": "Monthly"},
            {"id": "CNP16OV", "name": "Civilian Noninstitutional Population (16+)", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "SupplyChainModule": {
        "title": "Supply Chain (Inventory/Sales Ratios)",
        "description": (
            "Inventory-to-sales ratios across the supply chain. "
            "Rising ratios suggest slowing demand or inventory buildup; "
            "falling ratios indicate tight inventories or strong sales."
        ),
        "calculation": (
            "Inventory/Sales ratio = end-of-month inventories / monthly sales. "
            "A ratio of 1.3 means 1.3 months of inventory relative to the current sales pace."
        ),
        "data_sources": [
            {"id": "ISRATIO", "name": "Total Business Inventories/Sales Ratio", "frequency": "Monthly"},
            {"id": "RETAILIRSA", "name": "Retail Inventories/Sales Ratio", "frequency": "Monthly"},
            {"id": "MNFCTRIRSA", "name": "Manufacturing Inventories/Sales Ratio", "frequency": "Monthly"},
            {"id": "WHLSLRIRSA", "name": "Wholesale Inventories/Sales Ratio", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "RegionalPmiModule": {
        "title": "Regional PMI (Manufacturing Surveys)",
        "description": (
            "Regional Federal Reserve manufacturing surveys that serve as leading "
            "indicators for the national ISM PMI. Each survey covers its Fed district."
        ),
        "calculation": (
            "Diffusion index: positive = net expansion, negative = net contraction. "
            "These are survey-based, released ahead of the national ISM PMI, "
            "providing an early read on manufacturing conditions."
        ),
        "data_sources": [
            {"id": "GAFDISA066MSFRBNY", "name": "Empire State Manufacturing Index (NY Fed)", "frequency": "Monthly"},
            {"id": "GACDFSA066MSFRBPHI", "name": "Philadelphia Fed Manufacturing Index", "frequency": "Monthly"},
            {"id": "BACTSAMFRBDAL", "name": "Dallas Fed Manufacturing Index", "frequency": "Monthly"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "EnergyProductionModule": {
        "title": "Energy Production",
        "description": (
            "US mining and energy sector production index alongside crude oil prices. "
            "Shows the relationship between energy prices and domestic production activity."
        ),
        "calculation": (
            "Mining Production Index is part of the Industrial Production report (2017 = 100). "
            "WTI crude oil in dollars per barrel for context."
        ),
        "data_sources": [
            {"id": "IPMINE", "name": "Mining Sector Industrial Production Index", "frequency": "Monthly"},
            {"id": "DCOILWTICO", "name": "WTI Crude Oil Price", "frequency": "Daily"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },

    "RealRatesModule": {
        "title": "Real Rates / TIPS Yields",
        "description": (
            "Treasury Inflation-Protected Securities (TIPS) yields, which represent "
            "real (inflation-adjusted) interest rates. Negative real rates mean investors "
            "accept returns below expected inflation."
        ),
        "calculation": (
            "TIPS yield = nominal Treasury yield - breakeven inflation rate. "
            "Quoted as real yield to maturity. Negative real rates are stimulative; "
            "positive real rates are restrictive for borrowers."
        ),
        "data_sources": [
            {"id": "DFII5", "name": "5-Year TIPS Yield", "frequency": "Daily"},
            {"id": "DFII10", "name": "10-Year TIPS Yield", "frequency": "Daily"},
            {"id": "DFII20", "name": "20-Year TIPS Yield", "frequency": "Daily"},
            {"id": "DFII30", "name": "30-Year TIPS Yield", "frequency": "Daily"},
        ],
        "source": "Federal Reserve Economic Data (FRED)",
    },
}


def get_module_info(class_name: str) -> Optional[dict]:
    """Look up module info by class name. Returns None if not found."""
    return MODULE_INFO.get(class_name)
