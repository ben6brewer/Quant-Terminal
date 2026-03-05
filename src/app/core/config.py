from __future__ import annotations

from pathlib import Path

"""
Central configuration for the Quant Terminal application.
All application-wide constants and settings should be defined here.
"""

# Application metadata
APP_NAME = "Quant Terminal"
APP_VERSION = "0.2.0"
APP_ORGANIZATION = "QuantApp"

# Window settings
DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 900

# Chart settings
DEFAULT_TICKER = "BTC-USD"
DEFAULT_INTERVAL = "Daily"
DEFAULT_CHART_TYPE = "Candles"
DEFAULT_SCALE = "Logarithmic"
CANDLE_BAR_WIDTH = 0.6

# Data fetching
DEFAULT_PERIOD = "max"
DATA_FETCH_THREADS = True
SHOW_DOWNLOAD_PROGRESS = False

# Yahoo Finance Configuration (primary data source)
YAHOO_HISTORICAL_START = "1970-01-01"  # Earliest date to try fetching

# Interval mappings for yfinance (case-insensitive lookup)
INTERVAL_MAP = {
    "daily": "1d",
    "weekly": "1wk",
    "monthly": "1mo",
    "yearly": "1y",
    "Daily": "1d",
    "Weekly": "1wk",
    "Monthly": "1mo",
    "Yearly": "1y",
}

# Chart intervals (display names)
CHART_INTERVALS = ["Daily", "Weekly", "Monthly", "Yearly"]
CHART_TYPES = ["Candles", "Line"]
CHART_SCALES = ["Regular", "Logarithmic"]

# Theme settings
DEFAULT_THEME = "bloomberg"
AVAILABLE_THEMES = ["dark", "light", "bloomberg"]

# Module sections and navigation
# Each entry has "class" for dynamic import: "dotted.module.path:ClassName"
MODULE_SECTIONS = {
    "Charting": [
        {"id": "charts", "label": "Charts", "class": "app.ui.modules.chart.chart_module:ChartModule", "has_own_home_button": False},
    ],
    "Portfolio": [
        {"id": "portfolio_construction", "label": "Portfolio Construction", "class": "app.ui.modules.portfolio_construction:PortfolioConstructionModule"},
        {"id": "performance_metrics", "label": "Performance Metrics", "class": "app.ui.modules.performance_metrics:PerformanceMetricsModule"},
        {"id": "risk_analytics", "label": "Risk Analytics", "class": "app.ui.modules.risk_analytics:RiskAnalyticsModule"},
        {"id": "distribution_metrics", "label": "Distribution Metrics", "class": "app.ui.modules.return_distribution:ReturnDistributionModule"},
        {"id": "monte_carlo", "label": "Monte Carlo", "class": "app.ui.modules.monte_carlo:MonteCarloModule"},
    ],
    "Analysis": [
        {"id": "efficient_frontier", "label": "Efficient Frontier", "class": "app.ui.modules.analysis:EfficientFrontierModule"},
        {"id": "correlation_matrix", "label": "Correlation Matrix", "class": "app.ui.modules.analysis:CorrelationMatrixModule"},
        {"id": "covariance_matrix", "label": "Covariance Matrix", "class": "app.ui.modules.analysis:CovarianceMatrixModule"},
        {"id": "rolling_correlation", "label": "Rolling Correlation", "class": "app.ui.modules.analysis:RollingCorrelationModule"},
        {"id": "rolling_covariance", "label": "Rolling Covariance", "class": "app.ui.modules.analysis:RollingCovarianceModule"},
        {"id": "ols_regression", "label": "OLS Regression", "class": "app.ui.modules.analysis:OLSRegressionModule"},
        {"id": "monthly_returns", "label": "Monthly Returns", "class": "app.ui.modules.monthly_returns:MonthlyReturnsModule"},
        {"id": "asset_class_returns", "label": "Asset Class Returns", "class": "app.ui.modules.asset_class_returns:AssetClassReturnsModule"},
    ],
    "Macro": [
        {"id": "cpi", "label": "CPI", "class": "app.ui.modules.cpi:CpiModule"},
        {"id": "pce", "label": "PCE", "class": "app.ui.modules.pce:PceModule"},
        {"id": "ppi", "label": "PPI", "class": "app.ui.modules.ppi:PpiModule"},
        {"id": "inflation_expectations", "label": "Inflation Expectations", "class": "app.ui.modules.inflation_expectations:InflationExpectationsModule"},
        {"id": "yields", "label": "Yields", "class": "app.ui.modules.treasury:TreasuryModule"},
        {"id": "rate_probability", "label": "Rate Probabilities", "class": "app.ui.modules.rate_probability:RateProbabilityModule"},
        {"id": "labor_market_overview", "label": "Unemployment Rate", "class": "app.ui.modules.labor_market_overview:LaborMarketOverviewModule"},
        {"id": "demographics", "label": "Unemployment Demographics", "class": "app.ui.modules.demographics:DemographicsModule"},
        {"id": "payrolls", "label": "Payrolls", "class": "app.ui.modules.payrolls:PayrollsModule"},
        {"id": "labor_claims", "label": "Unemployment Claims", "class": "app.ui.modules.labor_claims:LaborClaimsModule"},
        {"id": "jolts", "label": "JOLTS", "class": "app.ui.modules.jolts:JoltsModule"},
        {"id": "money_supply", "label": "Money Supply", "class": "app.ui.modules.money_supply:MoneySupplyModule"},
        {"id": "fed_balance_sheet", "label": "Fed Balance Sheet", "class": "app.ui.modules.fed_balance_sheet:FedBalanceSheetModule"},
        {"id": "fed_funds_rate", "label": "Fed Funds Rate", "class": "app.ui.modules.fed_funds_rate:FedFundsRateModule"},
        {"id": "reserve_balances", "label": "Reserve Balances", "class": "app.ui.modules.reserve_balances:ReserveBalancesModule"},
        {"id": "money_velocity", "label": "Money Velocity", "class": "app.ui.modules.money_velocity:MoneyVelocityModule"},
    ],
    "_Settings": [
        {"id": "settings", "label": "Settings", "class": "app.ui.modules.settings_module:SettingsModule", "has_own_home_button": False},
    ],
}

# Flatten all modules for backward compatibility (exclude internal sections prefixed with _)
ALL_MODULES = [
    module
    for name, section_modules in MODULE_SECTIONS.items()
    if not name.startswith("_")
    for module in section_modules
]

# Tile settings
TILE_SCREENSHOT_DIR = Path.home() / ".quant_terminal" / "screenshots"
TILE_WIDTH = 453           # 3-column layout (16:9 aspect ratio, ~70% of original)
TILE_HEIGHT = 285          # 16:9 preview (453×255) + 30px label
TILE_COLS = 3              # 3-column grid
TILE_SPACING = 20

# Chart view settings
DEFAULT_VIEW_PERIOD_DAYS = 365  # Show last year by default
VIEW_PADDING_PERCENT = 0.05  # 5% padding on Y-axis

# Price formatting thresholds
PRICE_FORMAT_BILLION = 1e9
PRICE_FORMAT_THOUSAND = 1e3
PRICE_FORMAT_ONE = 1

# Equation parser settings
EQUATION_OPERATORS = {"+", "-", "*", "/"}
EQUATION_PREFIX = "="

# Error messages
ERROR_EMPTY_TICKER = "Ticker is empty."
ERROR_NO_DATA = "No data returned for ticker '{ticker}'."
ERROR_INVALID_EXPRESSION = "Invalid expression"
ERROR_NO_OVERLAPPING_DATES = "No overlapping dates found between tickers"

# Logging (for future implementation)
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
