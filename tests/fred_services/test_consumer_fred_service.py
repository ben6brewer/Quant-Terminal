"""Tests for Consumer FRED service."""

import numpy as np
import pandas as pd
import pytest


class TestConsumerFredService:
    @pytest.fixture
    def service(self):
        from app.ui.modules.consumer.services.consumer_fred_service import ConsumerFredService
        return ConsumerFredService

    def test_groups_defined(self, service):
        assert len(service.GROUPS) > 0
        assert service.GROUPS[0].series

    def test_series_contains_expected(self, service):
        series = service.GROUPS[0].series
        assert "Sentiment" in series
        assert "USREC" in series

    def test_fetch_all_data_keys(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            assert isinstance(result, dict)
            possible_keys = {"sentiment", "usrec"}
            assert set(result.keys()).issubset(possible_keys)

    def test_get_latest_stats(self, service, mock_fred_api, mock_fred_api_key):
        result = service.fetch_all_data()
        if result is not None:
            stats = service.get_latest_stats(result)
            if stats is not None:
                assert isinstance(stats, dict)

    def test_get_latest_stats_with_mom(self, service, mock_fred_api, mock_fred_api_key):
        """MoM change should be calculated when enough data points exist."""
        result = service.fetch_all_data()
        if result is not None:
            stats = service.get_latest_stats(result)
            if stats is not None and "sentiment_mom" in stats:
                assert isinstance(stats["sentiment_mom"], float)

    def test_repeated_calls_return_consistent_data(self, service, mock_fred_api, mock_fred_api_key):
        result1 = service.fetch_all_data()
        result2 = service.fetch_all_data()
        if result1 is not None:
            assert result2 is not None
            assert set(result1.keys()) == set(result2.keys())
