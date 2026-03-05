"""Tests for app.ui.modules.fred_base_module.FredDataModule."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules import fred_base_module as fbm


@pytest.mark.ui
class TestFredDataModule:
    def test_lookback_constants(self):
        """Lookback maps should have expected keys."""
        assert "1Y" in fbm.LOOKBACK_MONTHS
        assert "5Y" in fbm.LOOKBACK_MONTHS
        assert "Max" in fbm.LOOKBACK_MONTHS
        assert fbm.LOOKBACK_MONTHS["Max"] is None

    def test_lookback_weeks(self):
        assert "1Y" in fbm.LOOKBACK_WEEKS
        assert fbm.LOOKBACK_WEEKS["1Y"] == 52

    def test_lookback_quarters(self):
        assert "5Y" in fbm.LOOKBACK_QUARTERS
        assert fbm.LOOKBACK_QUARTERS["5Y"] == 20

    def test_slice_data_none(self):
        """Slicing None should return None."""
        mock_self = MagicMock()
        mock_self._current_lookback = "Max"
        mock_self.get_lookback_map.return_value = fbm.LOOKBACK_MONTHS
        result = FredDataModule.slice_data(mock_self, None)
        assert result is None

    def test_slice_data_max(self):
        """Max lookback should return full data."""
        mock_self = MagicMock()
        mock_self._current_lookback = "Max"
        mock_self.get_lookback_map.return_value = fbm.LOOKBACK_MONTHS

        dates = pd.date_range("2020-01-01", periods=100, freq="MS")
        df = pd.DataFrame({"value": range(100)}, index=dates)

        result = FredDataModule.slice_data(mock_self, df)
        assert len(result) == 100

    def test_slice_data_1y(self):
        """1Y lookback should return last 12 months."""
        mock_self = MagicMock()
        mock_self._current_lookback = "1Y"
        mock_self.get_lookback_map.return_value = fbm.LOOKBACK_MONTHS

        dates = pd.date_range("2020-01-01", periods=60, freq="MS")
        df = pd.DataFrame({"value": range(60)}, index=dates)

        result = FredDataModule.slice_data(mock_self, df)
        assert len(result) == 12
