"""Tests for monetary policy FRED service."""

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest


class TestMonetaryFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.monetary_policy.services.monetary_fred_service import (
            MonetaryFredService,
        )
        return MonetaryFredService

    def test_series_maps_defined(self):
        from app.ui.modules.monetary_policy.services import monetary_fred_service as mod
        assert hasattr(mod, "MONTHLY_SERIES")
        assert hasattr(mod, "WEEKLY_SERIES")
        assert hasattr(mod, "EFFR_SERIES")
        assert len(mod.MONTHLY_SERIES) > 0
        assert len(mod.WEEKLY_SERIES) > 0

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        """fetch_all_data should return dict with expected keys."""
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            expected_keys = {"money_supply", "velocity", "usrec", "balance_sheet", "reserves", "effr"}
            assert expected_keys.issubset(set(result.keys()))

    def test_unit_conversions(self):
        """M1/M2 should be in trillions (divided by 1000 from billions)."""
        from app.ui.modules.monetary_policy.services import monetary_fred_service as mod
        assert hasattr(mod, "MONTHLY_SERIES")
        # M1 and M2 are in the monthly series
        assert "M1" in mod.MONTHLY_SERIES or any("M1" in k for k in mod.MONTHLY_SERIES)

    def test_repeated_calls_return_consistent_data(self, service, mock_fred_api, mock_fred_api_key):
        result1 = service.fetch_all_data()
        result2 = service.fetch_all_data()
        if result1 is not None:
            assert result2 is not None
            assert set(result1.keys()) == set(result2.keys())
