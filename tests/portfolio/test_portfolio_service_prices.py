"""Characterization: PortfolioService methods that read prices (FakeYahoo), and
their handling of FREE CASH and ``[Custom]`` tickers.

``fetch_price_history`` is used as the oracle for exact values (so the checks
hold whatever close-price policy the pipeline adopts); goldens pin the FakeYahoo
numbers.
"""

from __future__ import annotations

import pytest

from app.services import custom_data_service as cds
from app.services.market_data import fetch_price_history
from app.ui.modules.portfolio_construction.services.portfolio_service import (
    PortfolioService,
)

from ._helpers import CUSTOM_NAME, PREFIX, assert_golden, daily_returns

PS = PortfolioService
BAD = f"{PREFIX}BAD"


def _close(ticker):
    return fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=True)["Close"]


@pytest.fixture
def custom_import(market_env):
    return cds.save_custom_import(CUSTOM_NAME, daily_returns(), "daily", "Equity", "_QT_TEST_src.csv")


class TestPrices:
    def test_fetch_current_prices(self, market_env):
        market_env.missing.add(BAD)
        prices = PS.fetch_current_prices(["AAPL", "SPY", "FREE CASH", "free cash", "", BAD])
        assert set(prices) == {"AAPL", "SPY", "FREE CASH", "free cash", BAD}
        assert prices["FREE CASH"] == 1.0 and prices["free cash"] == 1.0
        assert prices[BAD] is None
        assert prices["AAPL"] == _close("AAPL").iloc[-1]
        assert prices["SPY"] == _close("SPY").iloc[-1]
        assert PS.fetch_current_prices([]) == {}
        assert PS.fetch_current_prices(["FREE CASH"]) == {"FREE CASH": 1.0}
        assert_golden("current_prices", prices, area="service")

    def test_fetch_historical_closes_batch(self, market_env):
        market_env.missing.add(BAD)
        pairs = [("AAPL", "2026-06-26"), ("AAPL", "2026-06-27"), ("AAPL", "1970-01-02"),
                 ("AAPL", "2026-06-26"), ("SPY", "2026-06-30"), ("FREE CASH", "2026-06-27"),
                 (BAD, "2026-06-26")]
        out = PS.fetch_historical_closes_batch(pairs)
        aapl, spy = _close("AAPL"), _close("SPY")
        friday = aapl.loc["2026-06-26"]
        assert out == {
            "AAPL": {"2026-06-26": friday, "2026-06-27": friday, "1970-01-02": None},
            "SPY": {"2026-06-30": spy.loc["2026-06-30"]},
            "FREE CASH": {"2026-06-27": 1.0},
            BAD: {"2026-06-26": None},
        }
        assert PS.fetch_historical_closes_batch([]) == {}
        assert_golden("historical_closes_batch", out, area="service")

    def test_fetch_historical_close_price(self, market_env):
        aapl = _close("AAPL")
        assert PS.fetch_historical_close_price("AAPL", "2026-06-26") == aapl.loc["2026-06-26"]
        # Weekend / holiday -> the closest previous trading day.
        assert PS.fetch_historical_close_price("AAPL", "2026-06-28") == aapl.loc["2026-06-26"]
        assert PS.fetch_historical_close_price("AAPL", "2025-12-25") == aapl.loc["2025-12-24"]
        assert PS.fetch_historical_close_price("AAPL", "1970-01-02") is None
        assert PS.fetch_historical_close_price("free cash", "1970-01-02") == 1.0
        assert PS.fetch_historical_close_price("", "2026-06-26") is None
        market_env.missing.add(BAD)
        assert PS.fetch_historical_close_price(BAD, "2026-06-26") is None

    def test_first_available_date(self, market_env):
        market_env.missing.add(BAD)
        first = _close("AAPL").index.min()
        assert PS.get_first_available_date("AAPL") == first.strftime("%Y-%m-%d") == "1980-12-12"
        assert PS.get_first_available_date(BAD) is None


class TestValidation:
    @pytest.mark.parametrize("ticker, expected", [
        ("AAPL", (True, None)),
        (" spy ", (True, None)),
        ("FREE CASH", (True, None)),
        ("free cash ", (True, None)),
        ("", (False, "Ticker cannot be empty")),
        ("   ", (False, "Ticker cannot be empty")),
        ("brk b", (False, "Invalid ticker 'BRK B'. Ticker symbols cannot contain spaces.")),
    ])
    def test_is_valid_ticker(self, market_env, ticker, expected):
        assert PS.is_valid_ticker(ticker) == expected

    def test_is_valid_ticker_without_data(self, market_env):
        market_env.missing.add(BAD)
        ok, msg = PS.is_valid_ticker(BAD.lower())
        assert ok is False
        assert msg == f"Failed to fetch data for '{BAD}': No data returned for ticker '{BAD}'."

    @pytest.mark.parametrize("ticker, date, expected", [
        ("AAPL", "2026-06-26", (True, None)),
        ("aapl", "2026-06-27", (False, "2026-06-27 is a Saturday. Stock markets are closed on weekends.")),
        ("AAPL", "2026-06-28", (False, "2026-06-28 is a Sunday. Stock markets are closed on weekends.")),
        ("AAPL", "2025-12-25", (False, "2025-12-25 appears to be a market holiday. Please select a valid "
                                       "trading day.")),
        ("AAPL", "1980-12-01", (False, "No trading data available before 1980-12-12 for 'AAPL'.")),
        ("AAPL", "2026-07-06", (True, None)),  # after the last bar but not in the future
        ("AAPL", "2099-01-05", (False, "2099-01-05 is in the future.")),
        ("BTC-USD", "2026-06-27", (True, None)),  # crypto: any day
        ("FREE CASH", "2026-06-27", (True, None)),
        ("", "2026-06-27", (True, None)),
        ("AAPL", "", (True, None)),
        ("AAPL", "not-a-date", (True, None)),  # errors never block the user
    ])
    def test_is_valid_trading_day(self, market_env, ticker, date, expected):
        assert PS.is_valid_trading_day(ticker, date) == expected

    def test_is_valid_trading_day_crypto_and_cash_do_not_fetch(self, market_env):
        assert PS.is_valid_trading_day("ETH-USD", "2026-06-28") == (True, None)
        assert PS.is_valid_trading_day("FREE CASH", "2026-06-28") == (True, None)
        assert market_env.calls == []

    def test_is_valid_trading_day_without_data(self, market_env):
        market_env.missing.add(BAD)
        assert PS.is_valid_trading_day(BAD, "2026-06-26") == (True, None)


class TestNames:
    def test_fetch_ticker_names(self, market_env):
        names = PS.fetch_ticker_names(["AAPL", "spy", "FREE CASH", "", f"[custom] {PREFIX}anything"])
        assert set(names) == {"AAPL", "spy", "FREE CASH", f"[custom] {PREFIX}anything"}
        assert names["FREE CASH"] is None
        assert names[f"[custom] {PREFIX}anything"] == f"[custom] {PREFIX}anything"  # echoed verbatim
        assert names["AAPL"] == market_env.ticker_info("AAPL")["shortName"]
        assert names["spy"] == market_env.ticker_info("SPY")["shortName"]
        assert PS.fetch_ticker_names([]) == {}


class TestCustomTickers:
    def test_normalize_and_validate(self, custom_import):
        assert PS.normalize_ticker(f"[custom] {CUSTOM_NAME.lower()}") == f"[Custom] {CUSTOM_NAME}"
        assert PS.normalize_ticker(f"  [CUSTOM]   {CUSTOM_NAME.upper()} ") == f"[Custom] {CUSTOM_NAME}"
        assert PS.is_valid_ticker(f"[custom] {CUSTOM_NAME.lower()}") == (True, None)
        assert PS.is_valid_ticker(f" [Custom] {PREFIX}nope ") == (
            False, f"Unknown custom ticker '[Custom] {PREFIX}nope'. Import it first via Data → Import Data.")

    def test_prices_and_trading_days(self, custom_import, market_env):
        expected_last = cds.get_custom_prices(CUSTOM_NAME)["Close"].iloc[-1]
        ticker = f"[Custom] {CUSTOM_NAME}"
        assert PS.fetch_current_prices([ticker]) == {ticker: expected_last}
        closes = PS.fetch_historical_closes_batch([(ticker, "2024-06-29"), (ticker, "2023-12-29")])
        assert closes == {ticker: {"2024-06-29": expected_last, "2023-12-29": None}}
        assert PS.get_first_available_date(ticker) == "2024-01-01"
        assert PS.is_valid_trading_day(ticker, "2024-01-06") == (
            False, "2024-01-06 is a Saturday. Stock markets are closed on weekends.")
        assert PS.is_valid_trading_day(ticker, "2024-01-02") == (True, None)
        assert market_env.calls == []  # custom tickers never reach Yahoo

    def test_import_helpers_canonicalize_custom_tickers(self, custom_import):
        src = [{"id": "x", "date": "2024-01-02", "ticker": f"[custom] {CUSTOM_NAME.lower()}",
                "transaction_type": "Buy", "quantity": 1, "entry_price": 1, "fees": 0}]
        assert PS.generate_imported_transactions(src, True)[0]["ticker"] == f"[Custom] {CUSTOM_NAME}"
        assert PS.process_flat_import(src, True)[0]["ticker"] == f"[Custom] {CUSTOM_NAME}"
        with pytest.raises(ValueError, match="returns-only"):
            PS.create_transaction("2024-01-02", f"[Custom] {CUSTOM_NAME}", "Buy", 1, 1)

    def test_deleted_import_is_no_longer_valid(self, custom_import):
        assert cds.delete_custom_import(CUSTOM_NAME)
        ticker = f"[Custom] {CUSTOM_NAME}"
        assert PS.is_valid_ticker(ticker)[0] is False
        assert PS.normalize_ticker(ticker.lower()) == ticker.lower()
        assert PS.fetch_current_prices([ticker]) == {ticker: None}
