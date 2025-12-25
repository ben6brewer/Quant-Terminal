from __future__ import annotations

import re
import pandas as pd


def validate_ticker(ticker: str) -> tuple[bool, str]:
    """
    Validate a ticker symbol.
    
    Args:
        ticker: Ticker symbol to validate
        
    Returns:
        (is_valid, error_message) tuple
    """
    if not ticker:
        return False, "Ticker cannot be empty"
    
    ticker = ticker.strip()
    
    if not ticker:
        return False, "Ticker cannot be empty"
    
    # Basic ticker format validation
    # Allow letters, numbers, hyphens, dots, and equals sign for equations
    if not re.match(r'^[A-Za-z0-9.\-=+*/()]+$', ticker):
        return False, "Ticker contains invalid characters"
    
    return True, ""


def validate_interval(interval: str) -> tuple[bool, str]:
    """
    Validate a chart interval.
    
    Args:
        interval: Interval string
        
    Returns:
        (is_valid, error_message) tuple
    """
    valid_intervals = ["daily", "weekly", "monthly", "yearly", "1d", "1wk", "1mo", "1y"]
    
    if interval not in valid_intervals:
        return False, f"Invalid interval. Must be one of: {', '.join(valid_intervals)}"
    
    return True, ""


def validate_dataframe(df: pd.DataFrame, required_columns: list[str]) -> tuple[bool, str]:
    """
    Validate that a DataFrame has required columns.
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        
    Returns:
        (is_valid, error_message) tuple
    """
    if df is None:
        return False, "DataFrame is None"
    
    if df.empty:
        return False, "DataFrame is empty"
    
    missing = set(required_columns) - set(df.columns)
    if missing:
        return False, f"Missing required columns: {', '.join(sorted(missing))}"
    
    return True, ""


def validate_price_data(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Validate price data DataFrame has required OHLC columns.
    
    Args:
        df: Price data DataFrame
        
    Returns:
        (is_valid, error_message) tuple
    """
    required = ["Open", "High", "Low", "Close"]
    return validate_dataframe(df, required)


def validate_theme(theme: str) -> tuple[bool, str]:
    """
    Validate theme name.
    
    Args:
        theme: Theme name
        
    Returns:
        (is_valid, error_message) tuple
    """
    valid_themes = ["dark", "light"]
    
    if theme not in valid_themes:
        return False, f"Invalid theme. Must be one of: {', '.join(valid_themes)}"
    
    return True, ""
