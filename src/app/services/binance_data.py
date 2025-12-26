from __future__ import annotations

import requests
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class BinanceOrderBook:
    """
    Service for fetching order book depth data from Binance.
    
    Free API with no authentication required.
    Rate limit: 1200 requests per minute (20/second)
    """
    
    BASE_URL = "https://api.binance.com"
    
    # Mapping from yfinance ticker format to Binance symbol format
    TICKER_MAP = {
        "BTC-USD": "BTCUSDT",
        "ETH-USD": "ETHUSDT",
        "BNB-USD": "BNBUSDT",
        "XRP-USD": "XRPUSDT",
        "ADA-USD": "ADAUSDT",
        "DOGE-USD": "DOGEUSDT",
        "SOL-USD": "SOLUSDT",
        "DOT-USD": "DOTUSDT",
        "MATIC-USD": "MATICUSDT",
        "LTC-USD": "LTCUSDT",
        "AVAX-USD": "AVAXUSDT",
        "LINK-USD": "LINKUSDT",
        "UNI-USD": "UNIUSDT",
        "ATOM-USD": "ATOMUSDT",
        "XLM-USD": "XLMUSDT",
        "ALGO-USD": "ALGOUSDT",
        "VET-USD": "VETUSDT",
        "ICP-USD": "ICPUSDT",
        "FIL-USD": "FILUSDT",
        "TRX-USD": "TRXUSDT",
    }
    
    def __init__(self):
        self._cache = {}
        self._cache_duration = timedelta(seconds=5)  # Cache for 5 seconds
    
    @classmethod
    def is_binance_ticker(cls, ticker: str) -> bool:
        """Check if a ticker is supported by Binance."""
        ticker = ticker.strip().upper()
        return ticker in cls.TICKER_MAP
    
    @classmethod
    def get_binance_symbol(cls, ticker: str) -> Optional[str]:
        """Convert yfinance ticker to Binance symbol."""
        ticker = ticker.strip().upper()
        return cls.TICKER_MAP.get(ticker)
    
    def fetch_order_book(
        self, ticker: str, limit: int = 100
    ) -> Optional[Dict[str, List[Tuple[float, float]]]]:
        """
        Fetch order book depth data from Binance.
        
        Args:
            ticker: yfinance format ticker (e.g., "BTC-USD")
            limit: Number of price levels (5, 10, 20, 50, 100, 500, 1000, 5000)
        
        Returns:
            Dict with 'bids' and 'asks' as lists of (price, quantity) tuples,
            or None if fetch fails
        """
        # Check cache first
        cache_key = f"{ticker}_{limit}"
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_duration:
                return cached_data
        
        # Get Binance symbol
        symbol = self.get_binance_symbol(ticker)
        if not symbol:
            return None
        
        # Validate limit
        valid_limits = [5, 10, 20, 50, 100, 500, 1000, 5000]
        if limit not in valid_limits:
            limit = 100  # Default
        
        try:
            url = f"{self.BASE_URL}/api/v3/depth"
            params = {"symbol": symbol, "limit": limit}
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse bids and asks
            # Format: [["price", "quantity"], ...]
            bids = [(float(price), float(qty)) for price, qty in data.get("bids", [])]
            asks = [(float(price), float(qty)) for price, qty in data.get("asks", [])]
            
            result = {
                "bids": bids,  # Sorted descending by price
                "asks": asks,  # Sorted ascending by price
                "timestamp": datetime.now(),
            }
            
            # Cache the result
            self._cache[cache_key] = (result, datetime.now())
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Binance order book for {ticker}: {e}")
            return None
        except (KeyError, ValueError) as e:
            print(f"Error parsing Binance order book data: {e}")
            return None
    
    def get_depth_summary(
        self, ticker: str, levels: int = 10
    ) -> Optional[Dict[str, any]]:
        """
        Get a summary of order book depth.
        
        Args:
            ticker: yfinance format ticker
            levels: Number of levels to include in summary
        
        Returns:
            Dict with summary statistics
        """
        data = self.fetch_order_book(ticker, limit=levels)
        if not data:
            return None
        
        bids = data["bids"][:levels]
        asks = data["asks"][:levels]
        
        # Calculate total volume at each side
        bid_volume = sum(qty for _, qty in bids)
        ask_volume = sum(qty for _, qty in asks)
        
        # Calculate weighted average prices
        bid_weighted_price = (
            sum(price * qty for price, qty in bids) / bid_volume if bid_volume > 0 else 0
        )
        ask_weighted_price = (
            sum(price * qty for price, qty in asks) / ask_volume if ask_volume > 0 else 0
        )
        
        # Get best bid/ask
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        
        # Calculate spread
        spread = best_ask - best_bid if best_bid and best_ask else 0
        spread_pct = (spread / best_bid * 100) if best_bid else 0
        
        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "spread_pct": spread_pct,
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
            "bid_weighted_price": bid_weighted_price,
            "ask_weighted_price": ask_weighted_price,
            "bids": bids,
            "asks": asks,
            "timestamp": data["timestamp"],
        }
    
    def clear_cache(self):
        """Clear the order book cache."""
        self._cache.clear()