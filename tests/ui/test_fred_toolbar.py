"""Tests for FRED toolbar lookback combo behavior."""

import pytest

from app.ui.modules import fred_base_module as fbm


@pytest.mark.ui
class TestFredToolbarLookback:
    def test_lookback_months_sorted(self):
        """Lookback map keys should include standard durations."""
        keys = list(fbm.LOOKBACK_MONTHS.keys())
        assert "1Y" in keys
        assert "2Y" in keys
        assert "5Y" in keys
        assert "10Y" in keys
        assert "Max" in keys

    def test_lookback_values_ascending(self):
        """Non-None lookback values should be ascending."""
        values = [v for v in fbm.LOOKBACK_MONTHS.values() if v is not None]
        assert values == sorted(values)

    def test_weeks_values_ascending(self):
        values = [v for v in fbm.LOOKBACK_WEEKS.values() if v is not None]
        assert values == sorted(values)
