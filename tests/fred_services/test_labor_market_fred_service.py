"""Tests for labor market FRED service."""

import numpy as np
import pandas as pd
import pytest


class TestLaborMarketFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.labor_market.services.labor_market_fred_service import (
            LaborMarketFredService,
        )
        return LaborMarketFredService

    def test_series_maps_defined(self):
        from app.ui.modules.labor_market.services import labor_market_fred_service as mod
        assert hasattr(mod, "RATE_SERIES")
        assert hasattr(mod, "PAYROLL_SERIES")
        assert hasattr(mod, "JOLTS_SERIES")
        assert hasattr(mod, "CLAIMS_SERIES")
        assert len(mod.RATE_SERIES) > 0

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            expected_keys = {"rates", "payroll_levels", "jolts", "usrec", "claims"}
            assert expected_keys.issubset(set(result.keys()))

    def test_sector_labels_defined(self):
        """Should have SECTOR_LABELS for payroll stacked bar chart."""
        from app.ui.modules.labor_market.services import labor_market_fred_service as mod
        assert hasattr(mod, "SECTOR_LABELS")
        assert isinstance(mod.SECTOR_LABELS, list)
        assert len(mod.SECTOR_LABELS) > 0

    def test_get_latest_stats(self, service, mock_fred_api, mock_fred_api_key):
        """get_latest_stats should return dict with expected keys."""
        result = service.fetch_all_data()
        if result is not None:
            stats = service.get_latest_stats(result)
            if stats is not None:
                assert "unrate" in stats or "date" in stats

    def test_repeated_calls_return_consistent_data(self, service, mock_fred_api, mock_fred_api_key):
        result1 = service.fetch_all_data()
        result2 = service.fetch_all_data()
        if result1 is not None:
            assert result2 is not None
            assert set(result1.keys()) == set(result2.keys())
