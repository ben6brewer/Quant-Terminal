"""YFinance Data Module Base — Thin alias for FredDataModule without API key requirement."""

from __future__ import annotations

from app.ui.modules.fred_base_module import (
    FredDataModule,
    LOOKBACK_DAYS, LOOKBACK_WEEKS, LOOKBACK_MONTHS, LOOKBACK_QUARTERS,
)


class YFinanceDataModule(FredDataModule):
    """Base class for yfinance-powered data modules (no FRED API key needed)."""

    REQUIRES_API_KEY = False

    def get_lookback_map(self) -> dict:
        return LOOKBACK_DAYS
