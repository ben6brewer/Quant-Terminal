from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.config import (
    PRICE_FORMAT_BILLION,
    PRICE_FORMAT_THOUSAND,
    PRICE_FORMAT_ONE,
)


def format_price_usd(value: float) -> str:
    """
    Format a price value as USD string.
    
    Args:
        value: Price value to format
        
    Returns:
        Formatted price string (e.g., "$1,234.56")
    """
    if not np.isfinite(value):
        return ""
    
    if value >= PRICE_FORMAT_BILLION:
        return f"${value:,.0f}"
    if value >= PRICE_FORMAT_THOUSAND:
        return f"${value:,.2f}"
    if value >= PRICE_FORMAT_ONE:
        return f"${value:,.2f}"
    return f"${value:.6f}"


def format_date(dt: pd.Timestamp, format_str: str = "%Y-%m-%d") -> str:
    """
    Format a pandas Timestamp as a date string.
    
    Args:
        dt: Timestamp to format
        format_str: strftime format string
        
    Returns:
        Formatted date string
    """
    if dt is None or pd.isna(dt):
        return ""
    return dt.strftime(format_str)


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format a value as a percentage.
    
    Args:
        value: Value to format (e.g., 0.05 for 5%)
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string (e.g., "5.00%")
    """
    if not np.isfinite(value):
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def format_number(value: float, decimals: int = 2) -> str:
    """
    Format a number with thousands separators.
    
    Args:
        value: Number to format
        decimals: Number of decimal places
        
    Returns:
        Formatted number string
    """
    if not np.isfinite(value):
        return "N/A"
    return f"{value:,.{decimals}f}"


def format_large_number(value: float) -> str:
    """
    Format large numbers with abbreviations (K, M, B, T).
    
    Args:
        value: Number to format
        
    Returns:
        Formatted string (e.g., "1.5M", "2.3B")
    """
    if not np.isfinite(value):
        return "N/A"
    
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    
    if abs_value >= 1e12:
        return f"{sign}{abs_value/1e12:.2f}T"
    elif abs_value >= 1e9:
        return f"{sign}{abs_value/1e9:.2f}B"
    elif abs_value >= 1e6:
        return f"{sign}{abs_value/1e6:.2f}M"
    elif abs_value >= 1e3:
        return f"{sign}{abs_value/1e3:.2f}K"
    else:
        return f"{sign}{abs_value:.2f}"
