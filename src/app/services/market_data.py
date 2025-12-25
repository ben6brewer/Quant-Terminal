from __future__ import annotations

import pandas as pd
import yfinance as yf

from app.core.config import (
    INTERVAL_MAP,
    DEFAULT_PERIOD,
    DATA_FETCH_THREADS,
    SHOW_DOWNLOAD_PROGRESS,
    ERROR_EMPTY_TICKER,
    ERROR_NO_DATA,
)


def fetch_price_history(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Fetch historical price data for a ticker.
    
    Args:
        ticker: Ticker symbol (e.g., "BTC-USD", "AAPL")
        period: Time period (e.g., "max", "1y", "6mo")
        interval: Data interval (e.g., "1d", "daily", "weekly")
        
    Returns:
        DataFrame with OHLCV data
        
    Raises:
        ValueError: If ticker is empty or no data is returned
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError(ERROR_EMPTY_TICKER)

    interval_key = (interval or "1d").strip().lower()
    yf_interval = INTERVAL_MAP.get(interval_key)
    resample_yearly = False
    
    if yf_interval == "1y":
        resample_yearly = True
        yf_interval = "1mo"  # fetch monthly and roll up to yearly

    df = yf.download(
        tickers=ticker,
        period=period,
        interval=yf_interval,
        auto_adjust=False,
        progress=SHOW_DOWNLOAD_PROGRESS,
        threads=DATA_FETCH_THREADS,
    )

    if df is None or df.empty:
        raise ValueError(ERROR_NO_DATA.format(ticker=ticker))

    # Sometimes yfinance returns MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    # If user asked for annually, resample to year bars (OHLCV)
    if resample_yearly:
        ohlc = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
        }
        if "Volume" in df.columns:
            ohlc["Volume"] = "sum"

        df = df.resample("YE").agg(ohlc).dropna(how="any")

    return df
