"""Characterization: the chart module's TickerEquationParser evaluated on FakeYahoo.

Numeric checks use ``fetch_price_history`` itself as the oracle (so they hold
whatever close-price policy the pipeline adopts); goldens pin the actual values
on the FakeYahoo data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from golden_utils import assert_golden

from app.services.market_data import fetch_price_history
from app.ui.modules.chart.services.ticker_equation_parser import TickerEquationParser

from ._helpers import PREFIX

OHLC = ["Open", "High", "Low", "Close"]


@pytest.fixture
def parser():
    return TickerEquationParser()


def _prices(ticker, interval="1d"):
    return fetch_price_history(ticker, "max", interval)


def _common(*frames):
    idx = frames[0].index
    for f in frames[1:]:
        idx = idx.intersection(f.index)
    return idx


class TestIsEquationAndTokenize:
    @pytest.mark.parametrize("text, expected", [
        ("AAPL", False), ("BTC-USD", False), ("  BRK-B ", False), ("^GSPC", False),
        ("=AAPL", True), (" =BTC-USD", True), ("AAPL/SPY", True), ("AAPL*2", True), ("(AAPL)", True),
        ("AAPL + SPY", True), ("AAPL+ SPY", True), ("AAPL +SPY", True), ("AAPL+SPY", False),
        ("BTC-USD - ETH-USD", True), ("BTC-USD-ETH-USD", False), ("AAPL -SPY", False),
        ("", False),
    ])
    def test_is_equation(self, parser, text, expected):
        assert parser.is_equation(text) is expected

    @pytest.mark.parametrize("expr, tokens", [
        ("BTC-USD*2", ["BTC-USD", "*", "2"]),
        ("2*BTC-USD", ["2", "*", "BTC-USD"]),
        ("BTC-USD - ETH-USD", ["BTC-USD", "-", "ETH-USD"]),
        ("BTC-USD-ETH-USD", ["BTC-USD-ETH-USD"]),
        ("AAPL-SPY", ["AAPL-SPY"]),
        ("AAPL- SPY", ["AAPL", "-", "SPY"]),
        ("AAPL -SPY", ["AAPL", "-", "SPY"]),
        ("(AAPL+SPY)/2.5", ["(", "AAPL", "+", "SPY", ")", "/", "2.5"]),
        ("-AAPL", ["-", "AAPL"]),
        ("  aapl  /  spy ", ["aapl", "/", "spy"]),
    ])
    def test_tokenize(self, parser, expr, tokens):
        assert parser._tokenize(expr) == tokens

    @pytest.mark.parametrize("expr, rpn", [
        ("AAPL + SPY * 2", ["AAPL", "SPY", "2", "*", "+"]),
        ("(AAPL + SPY) * 2", ["AAPL", "SPY", "+", "2", "*"]),
        ("AAPL - SPY - QQQ", ["AAPL", "SPY", "-", "QQQ", "-"]),
        ("AAPL / SPY / 2", ["AAPL", "SPY", "/", "2", "/"]),
    ])
    def test_rpn_precedence_and_associativity(self, parser, expr, rpn):
        assert parser._infix_to_rpn(parser._tokenize(expr)) == rpn


class TestEvaluateOnFakeYahoo:
    def test_ratio_of_two_tickers(self, market_env, parser):
        result, desc = parser.parse_and_evaluate("=AAPL/SPY")
        assert desc == "=AAPL/SPY"
        assert list(result.columns) == OHLC
        aapl, spy = _prices("AAPL"), _prices("SPY")
        idx = _common(aapl, spy)
        assert result.index.equals(idx)
        for col in OHLC:
            np.testing.assert_allclose(result[col].to_numpy(),
                                       (aapl.loc[idx, col] / spy.loc[idx, col]).to_numpy())
        # AAPL history (1980) is longer than SPY (1993): the result starts at SPY's first bar.
        assert result.index[0] == spy.index[0]
        assert result.index[-1] == pd.Timestamp("2026-06-30")
        assert sorted({c["tickers"][0] for c in market_env.calls if c["period"] == "max"}) == ["AAPL", "SPY"]
        assert_golden("aapl_over_spy", result, area="equation")

    def test_description_without_prefix(self, market_env, parser):
        result, desc = parser.parse_and_evaluate("  AAPL + SPY ")
        assert desc == "=AAPL + SPY"
        aapl, spy = _prices("AAPL"), _prices("SPY")
        idx = _common(aapl, spy)
        np.testing.assert_allclose(result["Close"].to_numpy(),
                                   (aapl.loc[idx, "Close"] + spy.loc[idx, "Close"]).to_numpy())

    @pytest.mark.parametrize("expr, fn", [
        ("=AAPL + SPY * 2", lambda a, s, q: a + s * 2),
        ("=(AAPL + SPY) * 2", lambda a, s, q: (a + s) * 2),
        ("=AAPL - SPY - QQQ", lambda a, s, q: (a - s) - q),
        ("=AAPL / SPY / 2", lambda a, s, q: (a / s) / 2),
        ("=(AAPL + SPY + QQQ) / 3", lambda a, s, q: (a + s + q) / 3),
        ("=AAPL - AAPL", lambda a, s, q: a * 0),
    ])
    def test_arithmetic(self, market_env, parser, expr, fn):
        result, _ = parser.parse_and_evaluate(expr)
        frames = {t: _prices(t) for t in ("AAPL", "SPY", "QQQ")}
        tickers = [t for t in frames if t in expr]
        idx = _common(*[frames[t] for t in tickers])
        assert result.index.equals(idx)
        a, s, q = (frames[t].reindex(idx) for t in ("AAPL", "SPY", "QQQ"))
        for col in OHLC:
            np.testing.assert_allclose(result[col].to_numpy(), fn(a[col], s[col], q[col]).to_numpy())

    def test_single_ticker_scaled_keeps_full_history(self, market_env, parser):
        result, desc = parser.parse_and_evaluate("=BTC-USD*2")
        assert desc == "=BTC-USD*2"
        btc = _prices("BTC-USD")
        assert result.index.equals(btc.index)
        # BTC-USD history includes the bundled pre-Yahoo CSV (prepended by market_data).
        assert btc.index[0] < pd.Timestamp("2014-09-17")
        np.testing.assert_allclose(result["Close"].to_numpy(), btc["Close"].to_numpy() * 2)
        assert "Volume" not in result.columns
        assert_golden("btc_times_two", result, area="equation")

    def test_crypto_pair_seven_day_calendar(self, market_env, parser):
        result, _ = parser.parse_and_evaluate("=BTC-USD / ETH-USD")
        assert (result.index.dayofweek >= 5).any()  # weekends kept for crypto/crypto
        btc, eth = _prices("BTC-USD"), _prices("ETH-USD")
        assert result.index.equals(_common(btc, eth))
        assert result.index[0] == max(btc.index[0], eth.index[0])
        assert_golden("btc_over_eth", result, area="equation")

    def test_weekly_interval(self, market_env, parser):
        result, _ = parser.parse_and_evaluate("=AAPL/SPY", interval="weekly")
        aapl, spy = _prices("AAPL", "weekly"), _prices("SPY", "weekly")
        idx = _common(aapl, spy)
        assert result.index.equals(idx)
        assert (result.index.dayofweek == 6).all()  # resampled with pandas "W" (W-SUN)
        np.testing.assert_allclose(result["Close"].to_numpy(),
                                   (aapl.loc[idx, "Close"] / spy.loc[idx, "Close"]).to_numpy())
        assert_golden("aapl_over_spy_weekly", result, area="equation")

    def test_division_by_zero_gives_nan(self, market_env, parser):
        result, _ = parser.parse_and_evaluate("=AAPL / 0")
        assert result[OHLC].isna().all().all()
        result, _ = parser.parse_and_evaluate("=SPY / (AAPL - AAPL)")
        assert result[OHLC].isna().all().all()
        assert len(result) == len(_common(_prices("SPY"), _prices("AAPL")))

    def test_repeat_and_clear_cache_give_identical_results(self, market_env, parser):
        first, _ = parser.parse_and_evaluate("=AAPL/SPY")
        again, _ = parser.parse_and_evaluate("=AAPL/SPY")
        pd.testing.assert_frame_equal(first, again)
        parser.clear_cache()
        after_clear, _ = parser.parse_and_evaluate("=AAPL/SPY")
        pd.testing.assert_frame_equal(first, after_clear)
        # A new parser instance sees the same data.
        pd.testing.assert_frame_equal(first, TickerEquationParser().parse_and_evaluate("=AAPL/SPY")[0])


class TestErrors:
    def test_unknown_ticker(self, market_env, parser):
        market_env.missing.add(f"{PREFIX}BAD")
        with pytest.raises(ValueError, match=f"No data returned for ticker '{PREFIX}BAD'"):
            parser.parse_and_evaluate(f"=AAPL/{PREFIX}BAD")

    def test_no_overlapping_dates(self, market_env, parser):
        idx = pd.bdate_range("1985-01-02", periods=40)
        close = np.linspace(10.0, 12.0, len(idx))
        market_env.overrides[f"{PREFIX}OLD"] = pd.DataFrame(
            {"Open": close, "High": close, "Low": close, "Close": close, "Adj Close": close,
             "Volume": 1000.0}, index=idx)
        with pytest.raises(ValueError, match="No overlapping dates found between tickers"):
            parser.parse_and_evaluate(f"={PREFIX}OLD / SPY")

    @pytest.mark.parametrize("expr, pattern", [
        ("=AAPL +", r"Invalid expression: not enough operands for \+"),
        ("=AAPL SPY", r"^Invalid expression$"),
        ("=-AAPL", r"Invalid expression: not enough operands for -"),
    ])
    def test_invalid_expressions(self, market_env, parser, expr, pattern):
        with pytest.raises(ValueError, match=pattern):
            parser.parse_and_evaluate(expr)

    def test_constant_only_expression_raises_stop_iteration(self, market_env, parser):
        """No tickers -> nothing to take an index from; today this surfaces as StopIteration."""
        with pytest.raises(StopIteration):
            parser.parse_and_evaluate("=2 + 3")
        assert market_env.calls == []
