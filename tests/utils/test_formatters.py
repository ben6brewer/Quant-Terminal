"""Tests for app.utils.formatters."""

import math

import numpy as np
import pandas as pd
import pytest

from app.utils.formatters import (
    format_date,
    format_large_number,
    format_metric_value,
    format_number,
    format_percentage,
    format_price_usd,
)


# ── format_price_usd ──────────────────────────────────────────────────


class TestFormatPriceUsd:
    def test_billions(self):
        assert format_price_usd(1_500_000_000) == "$1,500,000,000"

    def test_thousands(self):
        assert format_price_usd(1234.56) == "$1,234.56"

    def test_ones(self):
        assert format_price_usd(5.99) == "$5.99"

    def test_sub_dollar(self):
        result = format_price_usd(0.001234)
        assert result == "$0.001234"

    def test_nan(self):
        assert format_price_usd(float("nan")) == ""

    def test_inf(self):
        assert format_price_usd(float("inf")) == ""

    def test_negative_inf(self):
        assert format_price_usd(float("-inf")) == ""

    def test_zero(self):
        assert format_price_usd(0.0) == "$0.000000"


# ── format_percentage ──────────────────────────────────────────────────


class TestFormatPercentage:
    def test_positive(self):
        assert format_percentage(0.05) == "5.00%"

    def test_negative(self):
        assert format_percentage(-0.123) == "-12.30%"

    def test_zero(self):
        assert format_percentage(0.0) == "0.00%"

    def test_custom_decimals(self):
        assert format_percentage(0.12345, decimals=1) == "12.3%"

    def test_nan(self):
        assert format_percentage(float("nan")) == "N/A"

    def test_inf(self):
        assert format_percentage(float("inf")) == "N/A"


# ── format_number ──────────────────────────────────────────────────────


class TestFormatNumber:
    def test_basic(self):
        assert format_number(1234.567) == "1,234.57"

    def test_nan(self):
        assert format_number(float("nan")) == "N/A"

    def test_custom_decimals(self):
        assert format_number(3.14159, decimals=4) == "3.1416"


# ── format_large_number ───────────────────────────────────────────────


class TestFormatLargeNumber:
    def test_trillions(self):
        assert format_large_number(1.5e12) == "1.50T"

    def test_billions(self):
        assert format_large_number(2.3e9) == "2.30B"

    def test_millions(self):
        assert format_large_number(7.8e6) == "7.80M"

    def test_thousands(self):
        assert format_large_number(5_432) == "5.43K"

    def test_small(self):
        assert format_large_number(42) == "42.00"

    def test_negative(self):
        assert format_large_number(-2.3e9) == "-2.30B"

    def test_nan(self):
        assert format_large_number(float("nan")) == "N/A"


# ── format_date ────────────────────────────────────────────────────────


class TestFormatDate:
    def test_basic(self):
        ts = pd.Timestamp("2024-03-15")
        assert format_date(ts) == "2024-03-15"

    def test_custom_format(self):
        ts = pd.Timestamp("2024-03-15")
        assert format_date(ts, "%b %Y") == "Mar 2024"

    def test_none(self):
        assert format_date(None) == ""

    def test_nat(self):
        assert format_date(pd.NaT) == ""


# ── format_metric_value ───────────────────────────────────────────────


class TestFormatMetricValue:
    def test_percent(self):
        assert format_metric_value(0.15, "percent") == "15.00"

    def test_ratio(self):
        assert format_metric_value(1.234, "ratio") == "1.23"

    def test_decimal(self):
        assert format_metric_value(0.567, "decimal") == "0.57"

    def test_decimal4(self):
        assert format_metric_value(0.5678, "decimal4") == "0.5678"

    def test_none_value(self):
        assert format_metric_value(None, "percent") == ""

    def test_nan_value(self):
        assert format_metric_value(float("nan"), "percent") == ""

    def test_zero_value(self):
        assert format_metric_value(0, "percent") == "--"

    def test_capture_tuple(self):
        # up=120, down=80 -> 120/80 = 1.50
        assert format_metric_value((120, 80), "capture") == "1.50"

    def test_capture_nan(self):
        assert format_metric_value((float("nan"), 80), "capture") == ""

    def test_capture_zero_denominator(self):
        assert format_metric_value((100, 0), "capture") == "--"
