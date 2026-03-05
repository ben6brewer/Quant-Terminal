"""Tests for app.services.base_fred_service.BaseFredService."""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.base_fred_service import BaseFredService


class TestIsCacheFresh:
    def test_fresh(self):
        last = date.today() - timedelta(days=5)
        assert BaseFredService._is_cache_fresh(last, max_age_days=7) is True

    def test_stale(self):
        last = date.today() - timedelta(days=50)
        assert BaseFredService._is_cache_fresh(last, max_age_days=45) is False

    def test_today(self):
        assert BaseFredService._is_cache_fresh(date.today(), max_age_days=1) is True

    def test_boundary(self):
        last = date.today() - timedelta(days=45)
        assert BaseFredService._is_cache_fresh(last, max_age_days=45) is True


class TestLoadSaveCache:
    def test_save_and_load(self, tmp_path):
        dates = pd.date_range("2020-01-01", periods=24, freq="MS")
        df = pd.DataFrame({"CPI": np.linspace(250, 270, 24)}, index=dates)
        cache_file = tmp_path / "test_cache.parquet"

        BaseFredService._save_cache(df, cache_file)
        assert cache_file.exists()

        loaded = BaseFredService._load_cache(cache_file, {"CPI": "CPIAUCSL"})
        assert loaded is not None
        assert len(loaded) == 24
        assert "CPI" in loaded.columns

    def test_load_nonexistent(self, tmp_path):
        result = BaseFredService._load_cache(
            tmp_path / "nonexistent.parquet", {"A": "B"}
        )
        assert result is None

    def test_load_filters_columns(self, tmp_path):
        dates = pd.date_range("2020-01-01", periods=12, freq="MS")
        df = pd.DataFrame(
            {"CPI": range(12), "Extra": range(12)},
            index=dates,
        )
        cache_file = tmp_path / "test.parquet"
        BaseFredService._save_cache(df, cache_file)

        # Only CPI in series_map
        loaded = BaseFredService._load_cache(cache_file, {"CPI": "CPIAUCSL"})
        assert "CPI" in loaded.columns
        assert "Extra" not in loaded.columns

    def test_load_empty_df(self, tmp_path):
        cache_file = tmp_path / "empty.parquet"
        pd.DataFrame().to_parquet(cache_file)
        result = BaseFredService._load_cache(cache_file, {"A": "B"})
        assert result is None


class TestComputeYoY:
    def test_basic(self):
        dates = pd.date_range("2020-01-01", periods=24, freq="MS")
        df = pd.DataFrame({"CPI": np.linspace(100, 120, 24)}, index=dates)
        result = BaseFredService._compute_yoy(df)
        assert not result.empty
        # First 12 values should be NaN (need 12 periods for YoY)
        assert result.iloc[11]["CPI"] != 0  # 12th value should have YoY
        assert len(result) > 0

    def test_empty(self):
        result = BaseFredService._compute_yoy(pd.DataFrame())
        assert result.empty

    def test_none(self):
        result = BaseFredService._compute_yoy(None)
        assert result.empty

    def test_values_are_percentage(self):
        """YoY should be in percentage form (multiplied by 100)."""
        dates = pd.date_range("2020-01-01", periods=24, freq="MS")
        # Constant 10% annual increase: each month 100, 110 a year later
        values = [100] * 12 + [110] * 12
        df = pd.DataFrame({"CPI": values}, index=dates)
        result = BaseFredService._compute_yoy(df)
        # The 13th value (index 12) should be ~10%
        yoy_value = result.iloc[0]["CPI"]  # First non-NaN
        assert abs(yoy_value - 10.0) < 0.1
