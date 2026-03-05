"""Tests for app.services.live_bar_aggregator.LiveBarAggregator."""

import pytest

from app.services.live_bar_aggregator import LiveBarAggregator


class TestLiveBarAggregator:
    @pytest.fixture
    def aggregator(self):
        return LiveBarAggregator()

    def test_initial_state(self, aggregator):
        assert aggregator.get_current_bar() is None
        assert aggregator.get_bar_count() == 0

    def test_add_first_bar(self, aggregator):
        bar = {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
            "start_ts": 1704067200,  # 2024-01-01
        }
        result = aggregator.add_minute_bar(bar)
        assert result is not None
        assert result["Open"] == 100.0
        assert result["Close"] == 100.5
        assert aggregator.get_bar_count() == 1

    def test_aggregates_high_low(self, aggregator):
        bar1 = {"open": 100, "high": 105, "low": 98, "close": 102, "volume": 1000, "start_ts": 1704067200}
        bar2 = {"open": 102, "high": 110, "low": 97, "close": 108, "volume": 2000, "start_ts": 1704067260}

        aggregator.add_minute_bar(bar1)
        result = aggregator.add_minute_bar(bar2)

        assert result["Open"] == 100  # First bar's open
        assert result["High"] == 110  # Max of all highs
        assert result["Low"] == 97  # Min of all lows
        assert result["Close"] == 108  # Last bar's close
        assert result["Volume"] == 3000  # Sum of volumes

    def test_reset(self, aggregator):
        bar = {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000, "start_ts": 1704067200}
        aggregator.add_minute_bar(bar)
        aggregator.reset()
        assert aggregator.get_current_bar() is None
        assert aggregator.get_bar_count() == 0

    def test_to_series(self, aggregator):
        bar = {"open": 100, "high": 105, "low": 98, "close": 102, "volume": 5000, "start_ts": 1704067200}
        aggregator.add_minute_bar(bar)
        series = aggregator.to_series()
        assert series is not None
        assert "Open" in series.index
        assert "Close" in series.index
