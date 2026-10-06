"""Deterministic builders shared by the tests in ``tests/portfolio``."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

import golden_utils

# This slice keeps its goldens in its own directory:
# tests/portfolio/goldens/<area>/<name>.json.
GOLDENS_DIR: Path = Path(__file__).resolve().parent / "goldens"
assert_golden = partial(golden_utils.assert_golden, goldens_dir=GOLDENS_DIR)

PREFIX = "_QT_TEST_"
CUSTOM_NAME = f"{PREFIX}Series"  # canonical, case-preserved custom import name


def tx(tx_id: str, date: str, ticker: str, kind: str, qty: float, price: float,
       fees: float = 0.0, seq: int = 0, notes: str = "") -> Dict[str, Any]:
    """A transaction dict in the exact shape PortfolioService.create_transaction builds."""
    return {
        "id": tx_id,
        "date": date,
        "ticker": ticker,
        "transaction_type": kind,
        "quantity": float(qty),
        "entry_price": float(price),
        "fees": float(fees),
        "notes": notes,
        "sequence": seq,
    }


def sample_ledger() -> List[Dict[str, Any]]:
    """A small, hand-checkable transaction ledger.

    Deposit 100k; buy AAPL/SPY; partial AAPL sell; open+close QQQ (flat);
    withdraw 5k with a $10 fee; buy MSFT (no price available later).
    """
    return [
        tx("t01", "2024-01-02", "FREE CASH", "Buy", 100000, 1.0, 0.0, 0),
        tx("t02", "2024-01-03", "AAPL", "Buy", 100, 185.0, 1.0, 0),
        tx("t03", "2024-01-03", "SPY", "Buy", 50, 470.0, 1.0, 1),
        tx("t04", "2024-02-01", "AAPL", "Sell", 40, 190.0, 1.0, 0),
        tx("t05", "2024-03-01", "QQQ", "Buy", 30, 440.0, 0.5, 0),
        tx("t06", "2024-03-15", "QQQ", "Sell", 30, 450.0, 0.5, 0),
        tx("t07", "2024-04-01", "FREE CASH", "Sell", 5000, 1.0, 10.0, 0),
        tx("t08", "2024-04-02", "MSFT", "Buy", 10, 420.0, 0.0, 0),
    ]


def daily_returns(start: str = "2024-01-01", end: str = "2024-06-28", seed: int = 7,
                  name: str = "returns") -> pd.Series:
    """Deterministic business-day decimal returns (float64, naive index)."""
    idx = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.0004, 0.01, len(idx)), index=idx, name=name)
