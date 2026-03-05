"""Tests for app.utils.validators."""

import pandas as pd
import pytest

from app.utils.validators import (
    validate_dataframe,
    validate_interval,
    validate_price_data,
    validate_theme,
    validate_ticker,
)


class TestValidateTicker:
    def test_valid_stock(self):
        valid, msg = validate_ticker("AAPL")
        assert valid is True
        assert msg == ""

    def test_valid_crypto(self):
        valid, msg = validate_ticker("BTC-USD")
        assert valid is True

    def test_valid_equation(self):
        valid, msg = validate_ticker("=AAPL+MSFT")
        assert valid is True

    def test_empty(self):
        valid, msg = validate_ticker("")
        assert valid is False
        assert "empty" in msg.lower()

    def test_whitespace_only(self):
        valid, msg = validate_ticker("   ")
        assert valid is False

    def test_invalid_chars(self):
        valid, msg = validate_ticker("AAPL$$$")
        assert valid is False
        assert "invalid" in msg.lower()


class TestValidateInterval:
    @pytest.mark.parametrize("interval", ["daily", "weekly", "monthly", "yearly", "1d", "1wk", "1mo", "1y"])
    def test_valid(self, interval):
        valid, msg = validate_interval(interval)
        assert valid is True

    def test_invalid(self):
        valid, msg = validate_interval("hourly")
        assert valid is False


class TestValidateDataframe:
    def test_valid(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        valid, msg = validate_dataframe(df, ["A", "B"])
        assert valid is True

    def test_none(self):
        valid, msg = validate_dataframe(None, ["A"])
        assert valid is False

    def test_empty(self):
        valid, msg = validate_dataframe(pd.DataFrame(), ["A"])
        assert valid is False

    def test_missing_columns(self):
        df = pd.DataFrame({"A": [1]})
        valid, msg = validate_dataframe(df, ["A", "B"])
        assert valid is False
        assert "B" in msg


class TestValidatePriceData:
    def test_valid(self):
        df = pd.DataFrame({"Open": [1], "High": [2], "Low": [0.5], "Close": [1.5]})
        valid, msg = validate_price_data(df)
        assert valid is True

    def test_missing_close(self):
        df = pd.DataFrame({"Open": [1], "High": [2], "Low": [0.5]})
        valid, msg = validate_price_data(df)
        assert valid is False


class TestValidateTheme:
    def test_valid(self):
        valid, msg = validate_theme("dark")
        assert valid is True

    def test_invalid(self):
        valid, msg = validate_theme("bloomberg")
        assert valid is False  # validator only has "dark" and "light"
