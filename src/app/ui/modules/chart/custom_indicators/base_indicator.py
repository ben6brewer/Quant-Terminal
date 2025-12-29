from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class BaseIndicator(ABC):
    """
    Base class for all custom indicators.
    
    Custom indicators should inherit from this class and implement
    the calculate() method.
    """
    
    # Metadata (subclasses should override these)
    NAME = "Base Indicator"
    DESCRIPTION = "Base indicator class"
    IS_OVERLAY = True  # True = plot on price chart, False = separate panel
    
    def __init__(self):
        """Initialize the indicator."""
        pass
    
    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Calculate the indicator values.
        
        Args:
            df: DataFrame with OHLCV data (columns: Open, High, Low, Close, Volume)
                Index should be DatetimeIndex
        
        Returns:
            DataFrame with indicator values, or None if calculation fails
            The returned DataFrame should have the same index as input df
            Column names will be used as legend labels
        """
        pass
    
    @classmethod
    def get_name(cls) -> str:
        """Get the indicator name."""
        return cls.NAME
    
    @classmethod
    def get_description(cls) -> str:
        """Get the indicator description."""
        return cls.DESCRIPTION
    
    @classmethod
    def is_overlay(cls) -> bool:
        """Check if indicator should be plotted on price chart."""
        return cls.IS_OVERLAY