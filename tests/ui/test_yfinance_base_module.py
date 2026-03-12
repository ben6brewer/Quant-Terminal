"""Tests for app.ui.modules.yfinance_base_module.YFinanceDataModule."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.ui.modules.yfinance_base_module import YFinanceDataModule
from app.ui.modules.fred_base_module import LOOKBACK_DAYS


@pytest.mark.ui
class TestYFinanceDataModule:
    def test_is_base_module_subclass(self):
        from app.ui.modules.base_module import BaseModule
        assert issubclass(YFinanceDataModule, BaseModule)

    def test_slice_data_none(self):
        mock_self = MagicMock()
        mock_self._current_lookback = "Max"
        mock_self.get_lookback_map.return_value = LOOKBACK_DAYS
        result = YFinanceDataModule.slice_data(mock_self, None)
        assert result is None

    def test_slice_data_max(self):
        mock_self = MagicMock()
        mock_self._current_lookback = "Max"
        mock_self.get_lookback_map.return_value = LOOKBACK_DAYS

        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        df = pd.DataFrame({"value": range(500)}, index=dates)

        result = YFinanceDataModule.slice_data(mock_self, df)
        assert len(result) == 500

    def test_slice_data_tail(self):
        mock_self = MagicMock()
        mock_self._current_lookback = "1Y"
        mock_self.get_lookback_map.return_value = LOOKBACK_DAYS

        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        df = pd.DataFrame({"value": range(500)}, index=dates)

        result = YFinanceDataModule.slice_data(mock_self, df)
        assert len(result) == LOOKBACK_DAYS["1Y"]

    def test_get_lookback_map_default(self):
        assert YFinanceDataModule.get_lookback_map(MagicMock()) == LOOKBACK_DAYS

    def test_get_fail_message_default(self):
        assert YFinanceDataModule.get_fail_message(MagicMock()) == "Failed to fetch data."
