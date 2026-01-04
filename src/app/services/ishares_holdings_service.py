"""iShares ETF Holdings Service - Fetches and parses ETF constituent data.

This service fetches holdings data from iShares CSV endpoints and provides
normalized constituent information for performance attribution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    pass


@dataclass
class ETFHolding:
    """Represents a single holding in an ETF."""

    ticker: str
    name: str
    sector: str
    weight: float  # As decimal (0.0665 = 6.65%)
    currency: str
    asset_class: str
    location: str


class ISharesHoldingsService:
    """Fetches and parses ETF holdings from iShares CSV endpoints."""

    # ETF URLs - add more as needed
    ETF_URLS = {
        "IWV": "https://www.ishares.com/us/products/239714/ishares-russell-3000-etf/1467271812596.ajax?fileType=csv&dataType=fund",
    }

    # iShares sector names mapped to standard GICS sectors
    SECTOR_MAP = {
        "Information Technology": "Technology",
        "Consumer Discretionary": "Consumer Cyclical",
        "Consumer Staples": "Consumer Defensive",
        "Health Care": "Healthcare",
        "Financials": "Financial Services",
        "Communication Services": "Communication Services",
        "Communication": "Communication Services",
        "Industrials": "Industrials",
        "Energy": "Energy",
        "Materials": "Basic Materials",
        "Real Estate": "Real Estate",
        "Utilities": "Utilities",
    }

    @classmethod
    def fetch_holdings(cls, etf_symbol: str = "IWV") -> Dict[str, ETFHolding]:
        """
        Fetch current holdings for an iShares ETF.

        Args:
            etf_symbol: ETF ticker symbol (default: IWV)

        Returns:
            Dict mapping ticker -> ETFHolding
            Empty dict if fetch fails
        """
        import requests

        url = cls.ETF_URLS.get(etf_symbol.upper())
        if not url:
            print(f"[ISharesHoldingsService] Unknown ETF: {etf_symbol}")
            return {}

        print(f"[ISharesHoldingsService] Fetching {etf_symbol} holdings from iShares...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            holdings = cls._parse_ishares_csv(response.text)
            print(f"[ISharesHoldingsService] Loaded {len(holdings)} holdings for {etf_symbol}")
            return holdings
        except requests.RequestException as e:
            print(f"[ISharesHoldingsService] Failed to fetch {etf_symbol}: {e}")
            return {}

    @classmethod
    def _parse_ishares_csv(cls, csv_content: str) -> Dict[str, ETFHolding]:
        """
        Parse messy iShares CSV format.

        The CSV has:
        - ~9 metadata rows at the top (fund info)
        - 1 header row with column names
        - Data rows until end or footer

        Args:
            csv_content: Raw CSV text

        Returns:
            Dict mapping ticker -> ETFHolding
        """
        import csv
        from io import StringIO

        holdings: Dict[str, ETFHolding] = {}
        lines = csv_content.strip().split("\n")

        # Find the header row (contains "Ticker" as first column)
        header_idx = None
        for i, line in enumerate(lines):
            if line.startswith("Ticker,") or line.startswith('"Ticker",'):
                header_idx = i
                break

        if header_idx is None:
            print("[ISharesHoldingsService] Could not find header row")
            return {}

        # Parse from header row onwards
        csv_data = "\n".join(lines[header_idx:])
        reader = csv.DictReader(StringIO(csv_data))

        for row in reader:
            try:
                holding = cls._parse_row(row)
                if holding:
                    holdings[holding.ticker] = holding
            except Exception as e:
                # Skip malformed rows
                ticker = row.get("Ticker", "unknown")
                print(f"[ISharesHoldingsService] Skipping row {ticker}: {e}")
                continue

        return holdings

    @classmethod
    def _parse_row(cls, row: Dict[str, str]) -> Optional[ETFHolding]:
        """
        Parse a single CSV row into an ETFHolding.

        Args:
            row: Dict from csv.DictReader

        Returns:
            ETFHolding or None if row should be skipped
        """
        ticker = row.get("Ticker", "").strip()
        asset_class = row.get("Asset Class", "").strip()

        # Skip non-equity holdings (cash, derivatives, etc.)
        if asset_class != "Equity":
            return None

        # Skip invalid tickers
        if not ticker or ticker == "-" or len(ticker) > 10:
            return None

        # Parse weight (remove % if present)
        weight_str = row.get("Weight (%)", "0").strip()
        weight_str = weight_str.replace("%", "").replace(",", "")
        try:
            weight = float(weight_str) / 100.0  # Convert to decimal
        except ValueError:
            weight = 0.0

        # Normalize sector
        raw_sector = row.get("Sector", "").strip()
        sector = cls._normalize_sector(raw_sector)

        return ETFHolding(
            ticker=ticker.upper(),
            name=row.get("Name", "").strip(),
            sector=sector,
            weight=weight,
            currency=row.get("Currency", "USD").strip(),
            asset_class=asset_class,
            location=row.get("Location", "").strip(),
        )

    @classmethod
    def _normalize_sector(cls, ishares_sector: str) -> str:
        """
        Map iShares sector names to standard sector names.

        Args:
            ishares_sector: Sector name from iShares CSV

        Returns:
            Normalized sector name
        """
        return cls.SECTOR_MAP.get(ishares_sector, ishares_sector or "Not Classified")

    @classmethod
    def get_available_etfs(cls) -> list[str]:
        """Return list of available ETF symbols."""
        return list(cls.ETF_URLS.keys())
