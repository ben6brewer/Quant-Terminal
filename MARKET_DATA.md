# Market Data Architecture

This document describes how market data is fetched, stored, updated, and refreshed across all modules in Quant Terminal.

---

## Data Sources

### Yahoo Finance (Sole Provider)
- **Use Case**: All historical data, batch loading, live polling
- **Library**: `yfinance` Python package
- **Rate Limits**: Unofficial API, no documented limits (be reasonable)
- **Docs**: https://github.com/ranaroussi/yfinance

---

## Storage Architecture

### Cache Directory Structure

```
~/.quant_terminal/
├── cache/
│   ├── AAPL.parquet          # Daily OHLCV data
│   ├── BTC-USD.parquet       # Crypto daily data
│   ├── MSFT.parquet
│   └── .data_source_version  # Tracks data source changes
├── portfolios/               # Portfolio JSON files
├── favorites.json            # Favorited modules
└── *_settings.json           # Module settings
```

### Parquet File Format

Each ticker's parquet file contains:

| Column | Type | Description |
|--------|------|-------------|
| Index | DatetimeIndex | Trading date (timezone-naive) |
| Open | float64 | Opening price |
| High | float64 | High price |
| Low | float64 | Low price |
| Close | float64 | Closing price |
| Volume | int64 | Trading volume |

---

## Module Data Flows

### Batch Processing (Portfolio/Analysis Modules)

For loading multiple tickers (portfolios, risk analysis, etc.), the system uses optimized batch processing:

```
┌─────────────────────────────────────────────────────────────────┐
│              fetch_price_history_batch(tickers)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   classify_tickers()   │
                    │   (Pre-sort by state) │
                    └───────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
            ┌───────────────┐       ┌───────────────┐
            │   Group A:    │       │   Group B:    │
            │ Cache Current │       │ Needs Update  │
            │ (just read)   │       │ (Yahoo fetch) │
            └───────────────┘       └───────────────┘
                    │                       │
                    ▼                       ▼
            ┌───────────────┐       ┌───────────────┐
            │ Read parquet  │       │ Batch         │
            │ (instant)     │       │ yf.download() │
            └───────────────┘       └───────────────┘
                    │                       │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Dict[ticker, DataFrame] │
                    └───────────────────────┘
```

**Classification Groups:**

| Group | Condition | Action |
|-------|-----------|--------|
| **A: Cache Current** | Cache exists and up-to-date | Read from parquet |
| **B: Needs Update** | No cache or cache outdated | Batch `yf.download()` |

**Large Batch Support (3000+ tickers):**

For large ticker lists like IWV constituents, `fetch_batch_full_history()` automatically
chunks into groups of ~200 and runs parallel `yf.download()` calls via ThreadPoolExecutor.

---

### Chart Module (Yahoo Finance)

```
┌─────────────────────────────────────────────────────────────────┐
│                      load_ticker_max(ticker)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Memory Cache Hit?   │
                    └───────────────────────┘
                         │            │
                        yes           no
                         │            │
                         ▼            ▼
                    [Return]    ┌─────────────────┐
                                │ Parquet Exists? │
                                └─────────────────┘
                                     │        │
                                    yes       no
                                     │        │
                                     ▼        ▼
                         ┌──────────────┐  ┌─────────────────────┐
                         │ Load Parquet │  │ Fresh Yahoo Fetch   │
                         └──────────────┘  │ (fetch_full_history)│
                                │          └─────────────────────┘
                                ▼                    │
                    ┌───────────────────────┐        │
                    │   Cache Current?      │        │
                    └───────────────────────┘        │
                         │            │              │
                        yes           no             │
                         │            │              │
                         │            ▼              │
                         │   ┌─────────────────┐     │
                         │   │ Incremental     │     │
                         │   │ Yahoo Update    │     │
                         │   └─────────────────┘     │
                         │            │              │
                         ▼            ▼              ▼
                    ┌─────────────────────────────────────┐
                    │         Save to Parquet             │
                    │         Update Memory Cache         │
                    └─────────────────────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │         Start Live Polling          │
                    └─────────────────────────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │                     │
                       [Crypto]              [Stock]
                          │                     │
                          ▼                     ▼
                    ┌───────────┐    ┌─────────────────────┐
                    │ Poll 24/7 │    │ Market Open?        │
                    │ (60s)     │    │ (4am-8pm ET)        │
                    └───────────┘    └─────────────────────┘
                                          │           │
                                         yes          no
                                          │           │
                                          ▼           ▼
                                    ┌──────────┐  [No Timer]
                                    │ Poll 60s │
                                    └──────────┘
```

#### Chart Module Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `fetch_price_history_yahoo()` | `market_data.py` | Main entry point for chart fetching |
| `_perform_yahoo_incremental_update()` | `market_data.py` | Fetch missing recent days |
| `YahooFinanceService.fetch_full_history()` | `yahoo_finance_service.py` | Fresh max history fetch |
| `YahooFinanceService.fetch_today_ohlcv()` | `yahoo_finance_service.py` | Live polling (today's bar) |

#### Chart Module Live Polling

| Asset Type | Timer | Interval | Condition |
|------------|-------|----------|-----------|
| Crypto (-USD, -USDT) | `_crypto_poll_timer` | 60 seconds | Always (24/7) |
| Stocks | `_stock_poll_timer` | 60 seconds | Only during extended hours |

**Extended Market Hours** (when stock polling runs):
- Pre-market: 4:00 AM - 9:30 AM ET
- Regular: 9:30 AM - 4:00 PM ET
- After-hours: 4:00 PM - 8:00 PM ET
- Excludes weekends and NYSE holidays

---

### Portfolio Construction (Live Price Updates)

Holdings tab polls Yahoo Finance every 60 seconds for live price updates during market hours.

**Behavior:**
- Polling starts when portfolio is loaded
- Pauses when module is hidden (hideEvent)
- Resumes when module is shown (showEvent)
- Crypto tickers (-USD, -USDT): update 24/7
- Stock tickers: only during extended hours (4am-8pm ET on trading days)

---

### Performance Metrics (Live Returns on Load)

Performance Metrics appends today's live return to historical returns when calculating metrics.

**Behavior:**
- Live return appended once on module load (not polling)
- Crypto: always eligible for live return
- Stocks: only during extended market hours
- If today's data already in cache: no additional fetch

---

## Cache Freshness Logic

### Stock Cache Freshness

A stock's cache is considered **current** if:
1. Last cached date >= last expected trading date

**Last Expected Trading Date** calculation:
- If today is a trading day AND market has closed (after 4 PM ET) → today
- Otherwise → most recent past trading day

### Crypto Cache Freshness

Crypto trades 24/7, so cache is current if:
- Last cached date >= yesterday (crypto always has today's partial data available)

### NYSE Trading Calendar

The system accounts for:
- Weekends (Saturday, Sunday)
- NYSE holidays (New Year's, MLK Day, Presidents' Day, Good Friday, Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas)

Holiday observance rules:
- Falls on Saturday → observed Friday
- Falls on Sunday → observed Monday

---

## Key Services

### MarketDataCache (`services/market_data_cache.py`)

Handles parquet file storage and retrieval.

```python
from app.services.market_data_cache import MarketDataCache

cache = MarketDataCache()

cache.has_cache("AAPL")         # Returns bool
df = cache.get_cached_data("AAPL")  # Returns DataFrame or None
cache.save_to_cache("AAPL", df)
cache.is_cache_current("AAPL")  # Returns bool
cache.clear_cache()
```

### YahooFinanceService (`services/yahoo_finance_service.py`)

Yahoo Finance wrapper for all data fetching.

```python
from app.services.yahoo_finance_service import YahooFinanceService

# Fetch date range
df = YahooFinanceService.fetch_historical("AAPL", "1970-01-01", "2019-12-31")

# Fetch today's bar (for live polling)
df = YahooFinanceService.fetch_today_ohlcv("AAPL")

# Fetch full history (fresh load)
df = YahooFinanceService.fetch_full_history("AAPL")

# Fetch full history with rate limit detection
df, was_rate_limited = YahooFinanceService.fetch_full_history_safe("AAPL")

# BATCH: Fetch multiple tickers (auto-chunks for 200+ tickers)
results, failed = YahooFinanceService.fetch_batch_full_history(
    ["AAPL", "MSFT", "GOOGL"],
    progress_callback=lambda completed, total, ticker: print(f"{completed}/{total}")
)

# BATCH: Fetch with per-ticker date ranges
results = YahooFinanceService.fetch_batch_date_range(
    ["AAPL", "MSFT"],
    date_ranges={"AAPL": ("2024-12-01", "2024-12-31"), "MSFT": ("2024-12-15", "2024-12-31")},
)

# BATCH: Fetch current live prices
prices = YahooFinanceService.fetch_batch_current_prices(["AAPL", "MSFT", "BTC-USD"])

# Validate ticker
is_valid = YahooFinanceService.is_valid_ticker("AAPL")
```

### Market Data Entry Points (`services/market_data.py`)

Main entry points for fetching market data.

```python
from app.services.market_data import (
    fetch_price_history,
    fetch_price_history_batch,
    fetch_price_history_yahoo,
    clear_cache,
)

# Single ticker
df = fetch_price_history("AAPL", period="max", interval="1d")

# BATCH: Multiple tickers with optimized grouping
results = fetch_price_history_batch(
    ["AAPL", "MSFT", "GOOGL", "AMZN"],
    progress_callback=lambda completed, total, ticker, phase: print(f"[{phase}] {ticker}")
)
# phase = "classifying" | "cache" | "yahoo"

# Chart module only
df = fetch_price_history_yahoo("AAPL", period="max", interval="1d")

# Clear cache
clear_cache("AAPL")  # Single ticker
clear_cache()         # All tickers
```

### Market Hours Utilities (`utils/market_hours.py`)

```python
from app.utils.market_hours import (
    is_crypto_ticker,
    is_nyse_trading_day,
    is_market_open_extended,
    get_last_expected_trading_date,
    is_stock_cache_current,
)
```

### ReturnsDataService (`services/returns_data_service.py`)

Cached daily returns with live return injection.

```python
from app.services.returns_data_service import ReturnsDataService

returns_df = ReturnsDataService.get_daily_returns("portfolio_name")
returns = ReturnsDataService.get_time_varying_portfolio_returns("portfolio_name")
returns = ReturnsDataService.get_ticker_returns("AAPL", start_date="2024-01-01")
updated = ReturnsDataService.append_live_return(returns, "AAPL")
updated = ReturnsDataService.append_live_portfolio_return(returns, "portfolio_name")
ReturnsDataService.invalidate_cache("portfolio_name")
```

---

## Configuration

### Config Constants (`core/config.py`)

```python
# Yahoo historical start (for backfill)
YAHOO_HISTORICAL_START = "1970-01-01"
```

---

## Testing & Debugging

### Clear All Cache

```python
from app.services.market_data_cache import MarketDataCache
MarketDataCache().clear_cache()
```

Or delete the directory:
```bash
rm -rf ~/.quant_terminal/cache/
```

### Check Cache Status

```python
from app.services.market_data_cache import MarketDataCache

cache = MarketDataCache()
ticker = "AAPL"

print(f"Has cache: {cache.has_cache(ticker)}")
print(f"Is current: {cache.is_cache_current(ticker)}")

df = cache.get_cached_data(ticker)
if df is not None:
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    print(f"Total bars: {len(df)}")
```

---

## Summary

### Module Data Sources

| Module | Entry Point | Storage | Live Updates |
|--------|-------------|---------|--------------|
| Chart | `fetch_price_history_yahoo()` | Parquet | Polling (60s) |
| Portfolio Construction | `fetch_price_history_batch()` | Parquet | Polling (60s) - Holdings tab |
| Performance Metrics | `ReturnsDataService` | Parquet | On-load (once) |
| Risk Analytics | `fetch_price_history_batch()` | Parquet | On-demand |
| Distribution | `fetch_price_history_batch()` | Parquet | On-demand |
