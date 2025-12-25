from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
import pandas as pd
import numpy as np
from PySide6.QtCore import Qt


class IndicatorService:
    """
    Service for calculating technical indicators.
    Implements indicators manually using pandas and numpy (no external dependencies).
    All indicators are user-created and persisted to disk.
    
    Now supports loading custom indicator plugins from Python files.
    """

    # Storage for user-created indicators (starts empty)
    OVERLAY_INDICATORS = {}
    OSCILLATOR_INDICATORS = {}
    ALL_INDICATORS = {}
    
    # Storage for custom indicator classes loaded from files
    CUSTOM_INDICATOR_CLASSES = {}

    # Path to save/load custom indicators
    _SAVE_PATH = Path.home() / ".quant_terminal" / "custom_indicators.json"
    
    # Path to custom indicator plugin files
    _PLUGIN_PATH = Path.home() / ".quant_terminal" / "custom_indicators"

    # Qt PenStyle mapping for JSON serialization
    _PENSTYLE_TO_STR = {
        Qt.SolidLine: "solid",
        Qt.DashLine: "dash",
        Qt.DotLine: "dot",
        Qt.DashDotLine: "dashdot",
    }
    
    _STR_TO_PENSTYLE = {
        "solid": Qt.SolidLine,
        "dash": Qt.DashLine,
        "dot": Qt.DotLine,
        "dashdot": Qt.DashDotLine,
    }

    @classmethod
    def _serialize_appearance(cls, appearance: Dict[str, Any]) -> Dict[str, Any]:
        """Convert appearance dict to JSON-serializable format."""
        if not appearance:
            return appearance
        
        serialized = appearance.copy()
        
        # Convert Qt.PenStyle to string
        if "line_style" in serialized:
            pen_style = serialized["line_style"]
            if isinstance(pen_style, Qt.PenStyle):
                serialized["line_style"] = cls._PENSTYLE_TO_STR.get(pen_style, "solid")
        
        return serialized
    
    @classmethod
    def _deserialize_appearance(cls, appearance: Dict[str, Any]) -> Dict[str, Any]:
        """Convert appearance dict from JSON format to runtime format."""
        if not appearance:
            return appearance
        
        deserialized = appearance.copy()
        
        # Convert string to Qt.PenStyle
        if "line_style" in deserialized:
            line_style_str = deserialized["line_style"]
            if isinstance(line_style_str, str):
                deserialized["line_style"] = cls._STR_TO_PENSTYLE.get(line_style_str, Qt.SolidLine)
        
        return deserialized

    @classmethod
    def initialize(cls) -> None:
        """Initialize the service and load saved indicators and plugins."""
        cls.load_indicators()
        cls.load_custom_indicator_plugins()

    @classmethod
    def load_custom_indicator_plugins(cls) -> None:
        """
        Load custom indicator plugins from the custom_indicators directory.
        
        Each plugin should be a Python file containing a class that inherits
        from BaseIndicator.
        """
        if not cls._PLUGIN_PATH.exists():
            cls._PLUGIN_PATH.mkdir(parents=True, exist_ok=True)
            print(f"Created custom indicators directory: {cls._PLUGIN_PATH}")
            return
        
        # Find all Python files in the plugin directory
        plugin_files = list(cls._PLUGIN_PATH.glob("*.py"))
        
        if not plugin_files:
            print(f"No custom indicator plugins found in {cls._PLUGIN_PATH}")
            return
        
        print(f"Loading custom indicator plugins from {cls._PLUGIN_PATH}")
        
        # CRITICAL FIX: Add the plugin directory to sys.path FIRST
        # This allows imports between plugin files to work (e.g., from base_indicator import BaseIndicator)
        plugin_path_str = str(cls._PLUGIN_PATH)
        if plugin_path_str not in sys.path:
            sys.path.insert(0, plugin_path_str)
        
        for plugin_file in plugin_files:
            try:
                # Skip __init__.py and base_indicator.py
                if plugin_file.name.startswith("__") or plugin_file.name == "base_indicator.py":
                    continue
                
                # Load the module
                module_name = plugin_file.stem
                spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                if spec is None or spec.loader is None:
                    print(f"  Failed to load spec for {plugin_file.name}")
                    continue
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # Find classes that inherit from BaseIndicator
                # We need to import BaseIndicator or check for the right methods
                indicator_classes = []
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        hasattr(attr, 'calculate') and 
                        hasattr(attr, 'NAME') and
                        attr_name != 'BaseIndicator'):
                        indicator_classes.append(attr)
                
                # Register each indicator class
                for indicator_class in indicator_classes:
                    cls._register_custom_indicator_class(indicator_class)
                    print(f"  Loaded: {indicator_class.NAME} from {plugin_file.name}")
                
            except Exception as e:
                print(f"  Error loading plugin {plugin_file.name}: {e}")
                import traceback
                traceback.print_exc()

    @classmethod
    def _register_custom_indicator_class(cls, indicator_class: Type[Any]) -> None:
        """Register a custom indicator class."""
        name = indicator_class.NAME
        is_overlay = indicator_class.IS_OVERLAY
        
        # Store the class
        cls.CUSTOM_INDICATOR_CLASSES[name] = indicator_class
        
        # Add to appropriate category
        # For plugin-based indicators, we use a special config that includes the class
        config = {"kind": "plugin", "class": name}
        
        cls.ALL_INDICATORS[name] = config
        
        if is_overlay:
            cls.OVERLAY_INDICATORS[name] = config
        else:
            cls.OSCILLATOR_INDICATORS[name] = config

    @classmethod
    def get_overlay_names(cls) -> List[str]:
        """Get list of overlay indicator names."""
        return sorted(list(cls.OVERLAY_INDICATORS.keys()))

    @classmethod
    def get_oscillator_names(cls) -> List[str]:
        """Get list of oscillator indicator names."""
        return sorted(list(cls.OSCILLATOR_INDICATORS.keys()))

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Get list of all indicator names."""
        return sorted(list(cls.ALL_INDICATORS.keys()))

    @classmethod
    def is_overlay(cls, indicator_name: str) -> bool:
        """Check if indicator is an overlay (plots on price chart)."""
        return indicator_name in cls.OVERLAY_INDICATORS

    @classmethod
    def add_custom_indicator(cls, name: str, config: dict, is_overlay: bool = True) -> None:
        """
        Add a custom indicator to the available indicators.
        
        Args:
            name: Display name for the indicator (e.g., "SMA(365)")
            config: Configuration dict with 'kind' and parameters
            is_overlay: True if overlay, False if oscillator
        """
        cls.ALL_INDICATORS[name] = config
        
        if is_overlay:
            cls.OVERLAY_INDICATORS[name] = config
        else:
            cls.OSCILLATOR_INDICATORS[name] = config
        
        # Auto-save after adding
        cls.save_indicators()

    @classmethod
    def remove_custom_indicator(cls, name: str) -> None:
        """
        Remove a custom indicator.
        Note: Cannot remove plugin-based indicators (they're loaded from files).
        """
        # Check if this is a plugin-based indicator
        if name in cls.CUSTOM_INDICATOR_CLASSES:
            print(f"Cannot remove plugin-based indicator '{name}'. Delete the plugin file instead.")
            return
        
        cls.ALL_INDICATORS.pop(name, None)
        cls.OVERLAY_INDICATORS.pop(name, None)
        cls.OSCILLATOR_INDICATORS.pop(name, None)
        
        # Auto-save after removing
        cls.save_indicators()

    @classmethod
    def save_indicators(cls) -> None:
        """
        Save all custom indicators to disk.
        Note: Plugin-based indicators are not saved here (they're in plugin files).
        """
        try:
            # Create directory if it doesn't exist
            cls._SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Filter out plugin-based indicators and serialize appearance
            overlays_to_save = {}
            for k, v in cls.OVERLAY_INDICATORS.items():
                if v.get("kind") != "plugin":
                    config = v.copy()
                    if "appearance" in config:
                        config["appearance"] = cls._serialize_appearance(config["appearance"])
                    overlays_to_save[k] = config
            
            oscillators_to_save = {}
            for k, v in cls.OSCILLATOR_INDICATORS.items():
                if v.get("kind") != "plugin":
                    config = v.copy()
                    if "appearance" in config:
                        config["appearance"] = cls._serialize_appearance(config["appearance"])
                    oscillators_to_save[k] = config
            
            # Prepare data to save
            data = {
                "overlays": overlays_to_save,
                "oscillators": oscillators_to_save,
            }
            
            # Write to JSON file
            with open(cls._SAVE_PATH, 'w') as f:
                json.dump(data, f, indent=2)
                
            saved_count = len(overlays_to_save) + len(oscillators_to_save)
            print(f"Saved {saved_count} indicators to {cls._SAVE_PATH}")
            
        except Exception as e:
            print(f"Error saving indicators: {e}")

    @classmethod
    def load_indicators(cls) -> None:
        """Load custom indicators from disk."""
        try:
            if not cls._SAVE_PATH.exists():
                print(f"No saved indicators found at {cls._SAVE_PATH}")
                return
            
            # Read from JSON file
            with open(cls._SAVE_PATH, 'r') as f:
                data = json.load(f)
            
            # Load overlays and deserialize appearance
            cls.OVERLAY_INDICATORS = {}
            for k, v in data.get("overlays", {}).items():
                config = v.copy()
                if "appearance" in config:
                    config["appearance"] = cls._deserialize_appearance(config["appearance"])
                cls.OVERLAY_INDICATORS[k] = config
            
            # Load oscillators and deserialize appearance
            cls.OSCILLATOR_INDICATORS = {}
            for k, v in data.get("oscillators", {}).items():
                config = v.copy()
                if "appearance" in config:
                    config["appearance"] = cls._deserialize_appearance(config["appearance"])
                cls.OSCILLATOR_INDICATORS[k] = config
            
            # Rebuild ALL_INDICATORS
            cls.ALL_INDICATORS = {**cls.OVERLAY_INDICATORS, **cls.OSCILLATOR_INDICATORS}
            
            print(f"Loaded {len(cls.ALL_INDICATORS)} indicators from {cls._SAVE_PATH}")
            
        except Exception as e:
            print(f"Error loading indicators: {e}")
            # Initialize with empty dicts on error
            cls.OVERLAY_INDICATORS = {}
            cls.OSCILLATOR_INDICATORS = {}
            cls.ALL_INDICATORS = {}

    @classmethod
    def calculate(
        cls, df: pd.DataFrame, indicator_name: str
    ) -> Optional[pd.DataFrame]:
        """
        Calculate a specific indicator.

        Args:
            df: DataFrame with OHLCV data
            indicator_name: Name of the indicator to calculate

        Returns:
            DataFrame with indicator values, or None if calculation fails
        """
        if indicator_name not in cls.ALL_INDICATORS:
            return None

        config = cls.ALL_INDICATORS[indicator_name]
        kind = config["kind"]

        try:
            # Check if this is a plugin-based indicator
            if kind == "plugin":
                return cls._calculate_plugin_indicator(df, indicator_name)
            
            # Built-in indicators
            if kind == "sma":
                return cls._calculate_sma(df, config["length"])
            elif kind == "ema":
                return cls._calculate_ema(df, config["length"])
            elif kind == "bbands":
                return cls._calculate_bbands(df, config["length"], config["std"])
            elif kind == "rsi":
                return cls._calculate_rsi(df, config["length"])
            elif kind == "macd":
                return cls._calculate_macd(df, config["fast"], config["slow"], config["signal"])
            elif kind == "atr":
                return cls._calculate_atr(df, config["length"])
            elif kind == "stochastic":
                return cls._calculate_stochastic(df, config["k"], config["d"], config["smooth_k"])
            elif kind == "obv":
                return cls._calculate_obv(df)
            elif kind == "vwap":
                return cls._calculate_vwap(df)
            return None

        except Exception as e:
            print(f"Error calculating {indicator_name}: {e}")
            return None

    @classmethod
    def _calculate_plugin_indicator(cls, df: pd.DataFrame, indicator_name: str) -> Optional[pd.DataFrame]:
        """Calculate a plugin-based custom indicator."""
        if indicator_name not in cls.CUSTOM_INDICATOR_CLASSES:
            print(f"Plugin class not found for {indicator_name}")
            return None
        
        try:
            # Get the indicator class
            indicator_class = cls.CUSTOM_INDICATOR_CLASSES[indicator_name]
            
            # Create an instance and calculate
            indicator_instance = indicator_class()
            result = indicator_instance.calculate(df)
            
            return result
            
        except Exception as e:
            print(f"Error calculating plugin indicator {indicator_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    @classmethod
    def calculate_multiple(
        cls, df: pd.DataFrame, indicator_names: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate multiple indicators.

        Args:
            df: DataFrame with OHLCV data
            indicator_names: List of indicator names to calculate

        Returns:
            Dictionary mapping indicator names to dicts containing:
                - "data": DataFrame with indicator values
                - "appearance": Appearance settings dict (or empty dict if none)
        """
        results = {}
        for name in indicator_names:
            result_df = cls.calculate(df, name)
            if result_df is not None:
                # Get appearance settings from config if available
                config = cls.ALL_INDICATORS.get(name, {})
                appearance = config.get("appearance", {})
                
                results[name] = {
                    "data": result_df,
                    "appearance": appearance,
                }
        return results

    # ========================
    # Indicator Implementations
    # ========================

    @staticmethod
    def _calculate_sma(df: pd.DataFrame, length: int) -> pd.DataFrame:
        """Calculate Simple Moving Average."""
        close = df["Close"]
        sma = close.rolling(window=length).mean()
        return pd.DataFrame({"SMA": sma}, index=df.index)

    @staticmethod
    def _calculate_ema(df: pd.DataFrame, length: int) -> pd.DataFrame:
        """Calculate Exponential Moving Average."""
        close = df["Close"]
        ema = close.ewm(span=length, adjust=False).mean()
        return pd.DataFrame({"EMA": ema}, index=df.index)

    @staticmethod
    def _calculate_bbands(df: pd.DataFrame, length: int, std: float) -> pd.DataFrame:
        """Calculate Bollinger Bands."""
        close = df["Close"]
        
        # Middle band is SMA
        middle = close.rolling(window=length).mean()
        
        # Standard deviation
        rolling_std = close.rolling(window=length).std()
        
        # Upper and lower bands
        upper = middle + (rolling_std * std)
        lower = middle - (rolling_std * std)
        
        return pd.DataFrame({
            "BB_Upper": upper,
            "BB_Middle": middle,
            "BB_Lower": lower,
        }, index=df.index)

    @staticmethod
    def _calculate_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
        """Calculate Relative Strength Index."""
        close = df["Close"]
        
        # Calculate price changes
        delta = close.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)
        
        # Calculate average gains and losses using EMA
        avg_gains = gains.ewm(span=length, adjust=False).mean()
        avg_losses = losses.ewm(span=length, adjust=False).mean()
        
        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return pd.DataFrame({"RSI": rsi}, index=df.index)

    @staticmethod
    def _calculate_macd(
        df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.DataFrame:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        close = df["Close"]
        
        # Calculate fast and slow EMAs
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line (EMA of MACD)
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        
        # Histogram
        histogram = macd_line - signal_line
        
        return pd.DataFrame({
            "MACD": macd_line,
            "MACDs": signal_line,
            "MACDh": histogram,
        }, index=df.index)

    @staticmethod
    def _calculate_stochastic(
        df: pd.DataFrame, k: int = 14, d: int = 3, smooth_k: int = 3
    ) -> pd.DataFrame:
        """Calculate Stochastic Oscillator."""
        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        
        # Lowest low and highest high over k periods
        lowest_low = low.rolling(window=k).min()
        highest_high = high.rolling(window=k).max()
        
        # %K (fast stochastic)
        k_fast = 100 * (close - lowest_low) / (highest_high - lowest_low)
        
        # Smooth %K
        k_slow = k_fast.rolling(window=smooth_k).mean()
        
        # %D (signal line)
        d_line = k_slow.rolling(window=d).mean()
        
        return pd.DataFrame({
            "STOCHk": k_slow,
            "STOCHd": d_line,
        }, index=df.index)

    @staticmethod
    def _calculate_atr(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
        """Calculate Average True Range."""
        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        
        # True Range calculation
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR is EMA of TR
        atr = tr.ewm(span=length, adjust=False).mean()
        
        return pd.DataFrame({"ATR": atr}, index=df.index)

    @staticmethod
    def _calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate On-Balance Volume."""
        if "Volume" not in df.columns:
            return None
        
        close = df["Close"]
        volume = df["Volume"]
        
        # Price direction
        price_change = close.diff()
        
        # OBV calculation
        obv = (np.sign(price_change) * volume).fillna(0).cumsum()
        
        return pd.DataFrame({"OBV": obv}, index=df.index)

    @staticmethod
    def _calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Volume Weighted Average Price."""
        if "Volume" not in df.columns:
            return None
        
        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        volume = df["Volume"]
        
        # Typical price
        typical_price = (high + low + close) / 3
        
        # VWAP calculation (cumulative)
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        
        return pd.DataFrame({"VWAP": vwap}, index=df.index)