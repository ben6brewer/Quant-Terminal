"""Tests for app.utils.recession_bands."""

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest


class TestAddRecessionBands:
    def test_empty_series(self):
        from app.utils.recession_bands import add_recession_bands

        plot_item = MagicMock()
        bands = add_recession_bands(plot_item, pd.Series(dtype=float), pd.DatetimeIndex([]))
        assert bands == []

    def test_none_series(self):
        from app.utils.recession_bands import add_recession_bands

        plot_item = MagicMock()
        bands = add_recession_bands(plot_item, None, pd.DatetimeIndex([]))
        assert bands == []

    def test_no_recession(self):
        from app.utils.recession_bands import add_recession_bands

        dates = pd.date_range("2020-01-01", periods=10)
        usrec = pd.Series(0, index=dates)
        plot_item = MagicMock()

        bands = add_recession_bands(plot_item, usrec, dates)
        assert bands == []
        plot_item.addItem.assert_not_called()

    def test_single_recession(self):
        from app.utils.recession_bands import add_recession_bands

        dates = pd.date_range("2020-01-01", periods=10)
        usrec = pd.Series([0, 0, 1, 1, 1, 0, 0, 0, 0, 0], index=dates)
        plot_item = MagicMock()

        bands = add_recession_bands(plot_item, usrec, dates)
        assert len(bands) == 1
        assert plot_item.addItem.call_count == 1

    def test_multiple_recessions(self):
        from app.utils.recession_bands import add_recession_bands

        dates = pd.date_range("2020-01-01", periods=10)
        usrec = pd.Series([1, 1, 0, 0, 1, 1, 0, 0, 1, 0], index=dates)
        plot_item = MagicMock()

        bands = add_recession_bands(plot_item, usrec, dates)
        assert len(bands) == 3
