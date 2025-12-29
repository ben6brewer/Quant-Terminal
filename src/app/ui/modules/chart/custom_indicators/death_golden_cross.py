from __future__ import annotations

from typing import Optional
import pandas as pd
import numpy as np

from base_indicator import BaseIndicator


class DeathGoldenCross(BaseIndicator):
    """
    Death Cross and Golden Cross indicator.
    
    - Golden Cross: 50-day SMA crosses above 200-day SMA (bullish signal)
    - Death Cross: 50-day SMA crosses below 200-day SMA (bearish signal)
    
    This indicator plots:
    - 50-day SMA
    - 200-day SMA
    - Markers at crossover points
    """
    
    NAME = "Death/Golden Cross"
    DESCRIPTION = "Detects 50/200 SMA crossovers"
    IS_OVERLAY = True  # Plot on price chart
    
    def __init__(self, short_period: int = 50, long_period: int = 200):
        """
        Initialize the Death/Golden Cross indicator.
        
        Args:
            short_period: Period for short-term SMA (default: 50)
            long_period: Period for long-term SMA (default: 200)
        """
        super().__init__()
        self.short_period = short_period
        self.long_period = long_period
    
    def calculate(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Calculate the Death/Golden Cross indicator.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            DataFrame with SMA values and crossover markers
        """
        if df is None or df.empty or "Close" not in df.columns:
            return None
        
        try:
            close = df["Close"]
            
            # Calculate SMAs
            sma_short = close.rolling(window=self.short_period).mean()
            sma_long = close.rolling(window=self.long_period).mean()
            
            # Detect crossovers
            # Golden Cross: short crosses above long (previous: short < long, current: short > long)
            # Death Cross: short crosses below long (previous: short > long, current: short < long)
            
            prev_short = sma_short.shift(1)
            prev_long = sma_long.shift(1)
            
            golden_cross = (prev_short < prev_long) & (sma_short > sma_long)
            death_cross = (prev_short > prev_long) & (sma_short < sma_long)
            
            # Create result DataFrame
            result = pd.DataFrame(index=df.index)
            result[f"SMA{self.short_period}"] = sma_short
            result[f"SMA{self.long_period}"] = sma_long
            
            # Add markers for crossovers (using the price at crossover point)
            # These will show as points on the chart
            result["Golden_Cross"] = np.where(golden_cross, close, np.nan)
            result["Death_Cross"] = np.where(death_cross, close, np.nan)
            
            return result
            
        except Exception as e:
            print(f"Error calculating Death/Golden Cross: {e}")
            return None