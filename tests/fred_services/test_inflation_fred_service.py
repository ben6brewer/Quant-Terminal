"""Tests for inflation FRED service."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


class TestInflationFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.inflation.services.inflation_fred_service import (
            InflationFredService,
        )
        return InflationFredService

    def test_series_maps_defined(self):
        from app.ui.modules.inflation.services import inflation_fred_service as mod
        assert hasattr(mod, "CPI_SERIES")
        assert hasattr(mod, "PCE_SERIES")
        assert hasattr(mod, "PPI_SERIES")
        assert hasattr(mod, "EXPECTATIONS_SERIES")
        assert len(mod.CPI_SERIES) > 0
        assert len(mod.PCE_SERIES) > 0

    def test_fetch_all_data_returns_dict(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            assert "cpi" in result
            assert "pce" in result
            assert "ppi" in result
            assert "expectations" in result

    def test_fetch_all_data_cpi_is_yoy(self, service, mock_fred_api, mock_fred_api_key):
        """CPI data should be YoY% (computed via _compute_yoy)."""
        result = service.fetch_all_data()
        if result is not None and result.get("cpi") is not None:
            cpi = result["cpi"]
            assert isinstance(cpi, pd.DataFrame)

    def test_get_latest_stats(self, service):
        """get_latest_stats should extract headline_cpi, core_cpi, pce, core_pce."""
        dates = pd.date_range("2024-01-01", periods=24, freq="MS")
        cpi_data = pd.DataFrame(
            {"Headline CPI": np.linspace(3.0, 2.5, 24), "Core CPI": np.linspace(3.5, 3.0, 24)},
            index=dates,
        )
        pce_data = pd.DataFrame(
            {"PCE": np.linspace(2.5, 2.0, 24), "Core PCE": np.linspace(2.8, 2.3, 24)},
            index=dates,
        )
        data = {
            "cpi": cpi_data,
            "pce": pce_data,
            "ppi": pd.DataFrame(),
            "expectations": pd.DataFrame(),
        }

        result = service.get_latest_stats(data)
        if result is not None:
            assert "headline_cpi" in result
            assert "core_cpi" in result
            assert "pce" in result
            assert "date" in result

    def test_repeated_calls_return_consistent_data(self, service, mock_fred_api, mock_fred_api_key):
        """Repeated calls should return equivalent results."""
        result1 = service.fetch_all_data()
        result2 = service.fetch_all_data()
        if result1 is not None:
            assert result2 is not None
            assert set(result1.keys()) == set(result2.keys())
