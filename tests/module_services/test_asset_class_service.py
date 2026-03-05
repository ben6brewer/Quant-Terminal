"""Tests for asset_class_returns.services.asset_class_returns_service."""

import pytest

from app.ui.modules.asset_class_returns.services.asset_class_returns_service import (
    AssetClassReturnsService,
)
from app.ui.modules.asset_class_returns.services import asset_class_returns_service as mod


class TestAssetClassConstants:
    def test_asset_classes_defined(self):
        assert hasattr(mod, "ASSET_CLASSES")
        assert len(mod.ASSET_CLASSES) >= 10

    def test_asset_class_tuples(self):
        """Each asset class should be (label, ticker, color_tuple)."""
        for entry in mod.ASSET_CLASSES:
            assert len(entry) == 3
            label, ticker, color = entry
            assert isinstance(label, str)
            assert isinstance(ticker, str)
            assert isinstance(color, tuple)
            assert len(color) == 3


class TestComputeTickerReturns:
    def test_basic(self):
        import numpy as np
        import pandas as pd

        dates = pd.date_range("2020-01-01", periods=1260, freq="B")
        close = pd.Series(
            100 * np.exp(np.cumsum(np.random.default_rng(42).normal(0.0003, 0.01, 1260))),
            index=dates,
        )
        year_returns, cagr = AssetClassReturnsService._compute_ticker_returns(close)
        assert isinstance(year_returns, dict)
        assert len(year_returns) > 0
        # Check years are integers
        for yr in year_returns:
            assert isinstance(yr, int)

    def test_cagr_reasonable(self):
        import numpy as np
        import pandas as pd

        dates = pd.date_range("2020-01-01", periods=1260, freq="B")
        close = pd.Series(
            100 * np.exp(np.cumsum(np.random.default_rng(42).normal(0.0003, 0.01, 1260))),
            index=dates,
        )
        _, cagr = AssetClassReturnsService._compute_ticker_returns(close)
        if cagr is not None:
            assert -0.5 < cagr < 1.0  # Reasonable CAGR range
