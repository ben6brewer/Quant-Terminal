"""Tests for rate_probability.services.rate_probability_service."""

import pytest

from app.ui.modules.rate_probability.services.rate_probability_service import (
    RateProbabilityService,
)


class TestContractTickers:
    def test_generates_tickers(self):
        tickers = RateProbabilityService._generate_contract_tickers(months_ahead=6)
        assert len(tickers) > 0
        for ticker_str, month, year in tickers:
            assert isinstance(ticker_str, str)
            assert 1 <= month <= 12
            assert year >= 2024

    def test_months_ahead(self):
        t6 = RateProbabilityService._generate_contract_tickers(months_ahead=6)
        t12 = RateProbabilityService._generate_contract_tickers(months_ahead=12)
        assert len(t12) > len(t6)


class TestRateConstants:
    def test_rate_step(self):
        from app.ui.modules.rate_probability.services import rate_probability_service as mod
        assert mod.RATE_STEP == 0.25

    def test_month_codes(self):
        from app.ui.modules.rate_probability.services import rate_probability_service as mod
        assert hasattr(mod, "MONTH_CODES")
        assert len(mod.MONTH_CODES) == 12


class TestImpliedRatePath:
    def test_returns_list(self):
        import pandas as pd
        import numpy as np

        # Create a simple probabilities DataFrame
        meetings = pd.date_range("2025-01-01", periods=3, freq="45D")
        probs_df = pd.DataFrame(
            {
                "425-450": [10, 15, 20],
                "450-475": [60, 50, 40],
                "475-500": [30, 35, 40],
            },
            index=meetings,
        )
        result = RateProbabilityService.get_implied_rate_path(probs_df)
        assert isinstance(result, list)
        assert len(result) == 3
        for meeting_str, rate in result:
            assert isinstance(rate, float)
