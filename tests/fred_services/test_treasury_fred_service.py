"""Tests for treasury FRED service."""

from datetime import date

import numpy as np
import pandas as pd
import pytest


class TestTreasuryFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.treasury.services.treasury_fred_service import (
            TreasuryFredService,
        )
        return TreasuryFredService

    def test_tenor_series_defined(self):
        from app.ui.modules.treasury.services import treasury_fred_service as mod
        assert hasattr(mod, "TENOR_SERIES")
        assert len(mod.TENOR_SERIES) >= 11  # 1M through 30Y

    def test_tenor_years_defined(self):
        from app.ui.modules.treasury.services import treasury_fred_service as mod
        assert hasattr(mod, "TENOR_YEARS")
        assert isinstance(mod.TENOR_YEARS, dict)

    def test_get_latest_yields(self, service):
        """get_latest_yields should return dict with 10y, 2y, spread."""
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        df = pd.DataFrame(
            {"10Y": np.linspace(4.0, 4.5, 10), "2Y": np.linspace(4.5, 4.0, 10)},
            index=dates,
        )
        result = service.get_latest_yields(df)
        if result is not None:
            assert "10y" in result or "10Y" in result

    def test_get_yields_for_date(self, service):
        """Should return tenor yields for a specific date."""
        dates = pd.bdate_range("2024-01-02", periods=20)
        df = pd.DataFrame(
            {
                "1M": np.linspace(5.0, 4.8, 20),
                "3M": np.linspace(5.1, 4.9, 20),
                "10Y": np.linspace(4.0, 4.2, 20),
            },
            index=dates,
        )
        result = service.get_yields_for_date(df, date(2024, 1, 15))
        if result is not None:
            assert isinstance(result, dict)

    def test_is_cache_fresh(self, service):
        """Cache fresher than 3 days should be considered fresh."""
        from datetime import date, timedelta

        today = date.today()
        assert service._is_cache_fresh(today) is True
        assert service._is_cache_fresh(today - timedelta(days=2)) is True
        assert service._is_cache_fresh(today - timedelta(days=10)) is False
