"""Tests for app.utils.market_hours."""

from datetime import date

import pytest

from app.utils.market_hours import (
    easter_date,
    get_nyse_holidays,
    is_crypto_ticker,
    is_nyse_trading_day,
)


class TestIsCryptoTicker:
    def test_btc_usd(self):
        assert is_crypto_ticker("BTC-USD") is True

    def test_eth_usdt(self):
        assert is_crypto_ticker("ETH-USDT") is True

    def test_stock(self):
        assert is_crypto_ticker("AAPL") is False

    def test_etf(self):
        assert is_crypto_ticker("SPY") is False

    def test_case_insensitive(self):
        assert is_crypto_ticker("btc-usd") is True

    def test_whitespace(self):
        assert is_crypto_ticker("  BTC-USD  ") is True


class TestEasterDate:
    """Known Easter dates to verify algorithm."""

    @pytest.mark.parametrize(
        "year, expected",
        [
            (2024, date(2024, 3, 31)),
            (2025, date(2025, 4, 20)),
            (2026, date(2026, 4, 5)),
            (2023, date(2023, 4, 9)),
        ],
    )
    def test_known_dates(self, year, expected):
        assert easter_date(year) == expected


class TestNyseHolidays:
    def test_2024_holidays_count(self):
        holidays = get_nyse_holidays(2024)
        # NYSE has 10 holidays per year
        assert len(holidays) == 10

    def test_christmas_2024(self):
        holidays = get_nyse_holidays(2024)
        assert date(2024, 12, 25) in holidays

    def test_good_friday_2024(self):
        holidays = get_nyse_holidays(2024)
        # Good Friday 2024 = March 29 (Easter is March 31)
        assert date(2024, 3, 29) in holidays

    def test_new_years_2024(self):
        holidays = get_nyse_holidays(2024)
        assert date(2024, 1, 1) in holidays

    def test_juneteenth_2024(self):
        holidays = get_nyse_holidays(2024)
        assert date(2024, 6, 19) in holidays

    def test_weekend_observed_shift(self):
        # July 4, 2026 is a Saturday, so observed on Friday July 3
        holidays = get_nyse_holidays(2026)
        assert date(2026, 7, 3) in holidays

    def test_caching(self):
        """Calling twice returns same frozenset (cached)."""
        h1 = get_nyse_holidays(2024)
        h2 = get_nyse_holidays(2024)
        assert h1 is h2


class TestIsNyseTradingDay:
    def test_weekday(self):
        # 2024-01-02 is Tuesday
        assert is_nyse_trading_day(date(2024, 1, 2)) is True

    def test_saturday(self):
        assert is_nyse_trading_day(date(2024, 1, 6)) is False

    def test_sunday(self):
        assert is_nyse_trading_day(date(2024, 1, 7)) is False

    def test_holiday(self):
        # MLK Day 2024 = Jan 15
        assert is_nyse_trading_day(date(2024, 1, 15)) is False

    def test_regular_monday(self):
        # Jan 8 2024 is a normal Monday
        assert is_nyse_trading_day(date(2024, 1, 8)) is True
