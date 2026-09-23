"""Characterization goldens: transactions -> positions/weights -> portfolio and ticker returns (P0.T5).

Inputs are fully deterministic and offline:

* ``tests/fixtures/portfolios/_QT_TEST_portfolio.json``: a transaction portfolio with
  AAPL, SPY, MSFT and BTC-USD plus FREE CASH, from 2025-01-02 to 2026-06-01. It has
  buys, a partial sell, a full exit and re-entry, a same-day sell->buy rotation,
  a Saturday crypto buy, a withdrawal, and fees. The app has no Dividend
  transaction type, so dividends are recorded the way a user would record them:
  as FREE CASH deposits (``notes`` say which).
* ``tests/fixtures/portfolios/_QT_TEST_weights_portfolio.json``: a weights-type
  portfolio (AAPL 40 / MSFT 25 / SPY 35).
* ``_QT_TEST_portfolio_nocash``: built in-test from the first fixture with the
  FREE CASH rows dropped. It covers the "no cash column" branch of
  ``calculate_cash_drag``.
* Prices come from FakeYahoo (``fake_yahoo`` fixture; data ends 2026-06-30). The
  four fixture tickers are served from ``HISTORY_START`` on, and BTC-USD
  earlier history comes from the bundled CSV. The app reads its caches, and
  the portfolio JSONs are copied, under a per-test ``fresh_home``.

The real clock (later than the fake data) matters in two places:
``PositionHistoryService`` extends positions to *today* when there is no
``end_date``, and ``LiveReturnService`` stamps the appended return with *today*.
The goldens pass explicit end dates. The clock-dependent behaviour is asserted
relative to ``pd.Timestamp.now()`` and never written to a golden.

Known bugs are strict xfails:

* KNOWN-BUG:weekly-anchor. ``ReturnsDataService._resample_returns`` (used by
  RDS and TRS) and ``market_data._resample_data`` resample weekly with ``"W"``
  (Sunday labels), but the factor data is ``W-FRI``, so weekly series never
  line up. The xfail asserts the desired Friday-anchored alignment.
* KNOWN-BUG:position-cash-ledger. ``PositionHistoryService`` counts only FREE
  CASH deposits and withdrawals as cash, so security buys and sells never
  debit or credit it. The UI ledger (``PortfolioService.calculate_free_cash_at_date``)
  does both, which leaves the analytics cash weight overstated.
* KNOWN-BUG:returns-cache-stale. ``ReturnsDataService.get_daily_returns`` stays
  valid until the portfolio file changes, so new price bars are never picked up.
* KNOWN-BUG:unadjusted-prices. Returns come from raw ``Close``; USER DECISION 4
  requires adjusted (total-return) closes.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fixtures.fake_yahoo import AS_OF, generate_history
from golden_utils import assert_golden, frame_digest

from app.services import market_data
from app.services.live_return_service import LiveReturnService
from app.services.portfolio_data_service import PortfolioDataService
from app.services.position_history_service import PositionHistoryService
from app.services.returns_data_service import ReturnsDataService
from app.services.ticker_metadata_service import TickerMetadataService
from app.services.ticker_returns_service import TickerReturnsService
from app.ui.modules.portfolio_construction.services.portfolio_persistence import (
    PortfolioPersistence,
)
from app.ui.modules.portfolio_construction.services.portfolio_service import (
    PortfolioService,
)

pytestmark = pytest.mark.golden

AREA = "returns"
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "portfolios"

PORTFOLIO = "_QT_TEST_portfolio"
WEIGHTS_PORTFOLIO = "_QT_TEST_weights_portfolio"
NOCASH_PORTFOLIO = "_QT_TEST_portfolio_nocash"

FIRST_TX = "2025-01-02"
END = "2026-06-30"  # == fake_yahoo.AS_OF
assert pd.Timestamp(END) == AS_OF
SECURITIES = ["AAPL", "BTC-USD", "MSFT", "SPY"]
CASH = "FREE CASH"

# Every transaction date, the calendar day before most of them, and weekend days.
CHECK_DATES = [
    "2025-01-02", "2025-01-04", "2025-02-02", "2025-02-03", "2025-03-17", "2025-04-14",
    "2025-04-15", "2025-05-09", "2025-05-10", "2025-05-11", "2025-06-16", "2025-07-01",
    "2025-09-01", "2025-09-02", "2025-11-14", "2026-01-04", "2026-01-05", "2026-03-16",
    "2026-05-31", "2026-06-01", "2026-06-30",
]

TICKER_START = "2024-01-01"

# FakeYahoo serves the fixture tickers from this date on (via ``overrides``, same code
# path as generated data), as if they listed then. That keeps each full-history
# download small. The app re-downloads on every call because the fake data is
# always "stale" against the real clock.
HISTORY_START = "2023-01-03"

# Price column the app computes returns and market values from TODAY (raw Close).
# When KNOWN-BUG:unadjusted-prices is fixed (P7 adjusted-price commit), flip this to
# "Adj Close". The oracles below then follow, and only the goldens need regenerating.
PRICE_FIELD = "Close"

# Live quote returns relative to the last fake close (see ``live_quotes``).
LIVE_BUMP = {"AAPL": -0.02, "MSFT": 0.005, "SPY": 0.01, "BTC-USD": 0.03}


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures and helpers
# ─────────────────────────────────────────────────────────────────────────────


def _raw_transactions(name: str = PORTFOLIO) -> list:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))["transactions"]


@pytest.fixture
def pf_env(fake_yahoo, fresh_home, monkeypatch):
    """FakeYahoo + a fresh home holding the fixture portfolios; in-memory caches reset."""
    monkeypatch.setattr(market_data, "_memory_cache", {})
    monkeypatch.setattr(market_data, "_live_bar_cache", {})
    monkeypatch.setattr(ReturnsDataService, "_memory_cache", {})
    monkeypatch.setattr(TickerMetadataService, "_cache", None)
    for ticker in SECURITIES:
        fake_yahoo.overrides[ticker] = generate_history(ticker).loc[HISTORY_START:]

    pdir = PortfolioPersistence._PORTFOLIOS_DIR
    assert fresh_home in pdir.parents, pdir
    assert PortfolioDataService._PORTFOLIOS_DIR == pdir
    assert fresh_home in ReturnsDataService._CACHE_DIR.parents
    assert fresh_home in market_data.MarketDataCache._CACHE_DIR.parents
    pdir.mkdir(parents=True, exist_ok=True)
    for src in sorted(FIXTURE_DIR.glob("_QT_TEST_*.json")):
        shutil.copyfile(src, pdir / src.name)

    raw = json.loads((FIXTURE_DIR / f"{PORTFOLIO}.json").read_text(encoding="utf-8"))
    raw["name"] = NOCASH_PORTFOLIO
    raw["transactions"] = [t for t in raw["transactions"] if t["ticker"] != CASH]
    (pdir / f"{NOCASH_PORTFOLIO}.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return fake_yahoo


@pytest.fixture
def live_quotes(pf_env, monkeypatch):
    """Serve "live" quotes one day after ``as_of`` with a close of ``last_close * (1 + LIVE_BUMP)``.

    Only ``period="5d"`` downloads see the extra bar. That is the
    ``fetch_batch_current_prices`` path. ``fetch_price_history`` always pulls
    ``period="max"``, so "yesterday's close" stays the last fake close.
    """
    ctl = pf_env
    original = ctl.history

    def history(ticker, start=None, end=None, period=None):
        df = original(ticker, start=start, end=end, period=period)
        bump = LIVE_BUMP.get(ticker.upper())
        if period == "5d" and bump is not None and len(df):
            price = float(df["Close"].iloc[-1]) * (1.0 + bump)
            row = pd.DataFrame(
                {"Open": price, "High": price, "Low": price, "Close": price,
                 "Adj Close": price, "Volume": 1_000},
                index=pd.DatetimeIndex([ctl.as_of + pd.Timedelta(days=1)], name="Date"),
            )
            df = pd.concat([df, row])
        return df

    monkeypatch.setattr(ctl, "history", history)
    return LIVE_BUMP


def _sorted_cols(df: pd.DataFrame) -> pd.DataFrame:
    # PositionHistoryService builds its columns from a set, so the order changes with PYTHONHASHSEED.
    return df.reindex(sorted(df.columns), axis=1)


def _digest(obj):
    if isinstance(obj, pd.DataFrame):
        obj = _sorted_cols(obj)
    return frame_digest(obj)


def _rows(df: pd.DataFrame, dates=CHECK_DATES) -> dict:
    out = {}
    for d in dates:
        ts = pd.Timestamp(d)
        out[d] = None if ts not in df.index else {c: float(df.at[ts, c]) for c in sorted(df.columns)}
    return out


def _points(s: pd.Series, dates) -> dict:
    return {d: (float(s.loc[pd.Timestamp(d)]) if pd.Timestamp(d) in s.index else None) for d in dates}


def _close(ticker: str) -> pd.Series:
    return generate_history(ticker)[PRICE_FIELD]


def _expected_positions(index: pd.DatetimeIndex, include_cash: bool = True) -> pd.DataFrame:
    """Independent oracle: cumulative signed quantities by transaction date."""
    txs = [t for t in _raw_transactions() if include_cash or t["ticker"] != CASH]
    cols = sorted({t["ticker"] for t in txs})
    out = pd.DataFrame(0.0, index=index, columns=cols)
    for tx in sorted(txs, key=lambda t: (t["date"], t["sequence"])):
        sign = 1.0 if tx["transaction_type"] == "Buy" else -1.0
        out.loc[out.index >= pd.Timestamp(tx["date"]), tx["ticker"]] += sign * tx["quantity"]
    return out


def _expected_weights(positions: pd.DataFrame) -> pd.DataFrame:
    """Independent oracle: market value (PRICE_FIELD, calendar-day ffill) over total value."""
    mv = pd.DataFrame(index=positions.index)
    for col in positions.columns:
        if col == CASH:
            mv[col] = positions[col]
        else:
            mv[col] = positions[col] * _close(col).reindex(positions.index, method="ffill")
    mv = mv.fillna(0.0)
    return mv.div(mv.sum(axis=1), axis=0)


def _expected_portfolio_returns(weights: pd.DataFrame) -> pd.Series:
    """Independent oracle: sum(w_t * r_t) on the weights/returns date intersection."""
    rets = pd.DataFrame({t: _close(t).pct_change() for t in SECURITIES if t in weights.columns})
    common = weights.index.intersection(rets.index)
    secs = [c for c in weights.columns if c != CASH]
    return (weights.loc[common, secs] * rets.loc[common, secs].fillna(0.0)).sum(axis=1)


def _time_under_water_vectorized(returns: pd.Series) -> pd.Series:
    cum = (1 + returns).cumprod()
    under = cum < cum.cummax()
    return under.astype(int).groupby((~under).cumsum()).cumsum()


# ─────────────────────────────────────────────────────────────────────────────
# Fixture sanity
# ─────────────────────────────────────────────────────────────────────────────


def test_fixture_portfolios_load(pf_env):
    before = (PortfolioPersistence._PORTFOLIOS_DIR / f"{PORTFOLIO}.json").read_bytes()
    txs = PortfolioDataService.get_transactions(PORTFOLIO)
    assert len(txs) == 15
    assert PortfolioDataService.get_tickers(PORTFOLIO) == ["AAPL", "SPY", "MSFT", "BTC-USD"]
    assert not PortfolioDataService.is_weights_portfolio(PORTFOLIO)
    assert PortfolioDataService.is_weights_portfolio(WEIGHTS_PORTFOLIO)
    assert PortfolioDataService.get_weights(WEIGHTS_PORTFOLIO) == {"AAPL": 0.4, "MSFT": 0.25, "SPY": 0.35}
    assert PortfolioDataService.get_tickers(WEIGHTS_PORTFOLIO) == ["AAPL", "MSFT", "SPY"]
    # Every fixture transaction has a "sequence", so loading never re-saves the file.
    assert (PortfolioPersistence._PORTFOLIOS_DIR / f"{PORTFOLIO}.json").read_bytes() == before


def test_holdings_golden(pf_env):
    prices = {t: float(_close(t).iloc[-1]) for t in SECURITIES}
    holdings = PortfolioDataService.get_holdings(PORTFOLIO, prices)
    by_ticker = {h.ticker: h for h in holdings}
    assert set(by_ticker) == set(SECURITIES)
    assert by_ticker["AAPL"].quantity == pytest.approx(60.0)
    assert by_ticker["SPY"].quantity == pytest.approx(80.0)
    assert by_ticker["MSFT"].quantity == pytest.approx(25.0)
    assert by_ticker["BTC-USD"].quantity == pytest.approx(0.15)
    assert sum(h.weight for h in holdings) == pytest.approx(1.0)
    # get_holdings reads a "total_cost" key that calculate_aggregate_holdings never
    # sets, so Holding.total_cost is always 0.
    assert all(h.total_cost == 0 for h in holdings)
    cash = PortfolioService.calculate_free_cash_summary(_raw_transactions())
    data = {
        "order": [h.ticker for h in holdings],
        "holdings": {
            h.ticker: {
                "quantity": h.quantity, "avg_cost_basis": h.avg_cost_basis, "total_cost": h.total_cost,
                "current_price": h.current_price, "market_value": h.market_value, "pnl": h.pnl,
                "weight": h.weight,
            }
            for h in holdings
        },
        "ui_free_cash_balance": cash["quantity"],
        "weights_portfolio": {h.ticker: h.weight for h in PortfolioDataService.get_holdings(WEIGHTS_PORTFOLIO)},
    }
    assert_golden("holdings", data, area=AREA)


# ─────────────────────────────────────────────────────────────────────────────
# Positions and weights over time
# ─────────────────────────────────────────────────────────────────────────────


def test_position_history_golden(pf_env):
    pos = PositionHistoryService.get_position_history(PORTFOLIO, end_date=END)
    full_index = pd.date_range(FIRST_TX, END, freq="D")
    assert pos.index.equals(full_index)
    assert sorted(pos.columns) == sorted(SECURITIES + [CASH])
    pd.testing.assert_frame_equal(
        _sorted_cols(pos), _expected_positions(full_index), check_freq=False, rtol=1e-12
    )
    last = pos.loc[pd.Timestamp(END)]
    assert last["AAPL"] == pytest.approx(60.0)
    assert last["SPY"] == pytest.approx(80.0)
    assert last["MSFT"] == pytest.approx(25.0)
    assert last["BTC-USD"] == pytest.approx(0.15)
    assert last[CASH] == pytest.approx(100000 + 48 + 95.4 - 5000 + 52.5)
    # The same-day MSFT full exit and SPY add both show up in the 2025-09-02 row.
    assert pos.at[pd.Timestamp("2025-09-02"), "MSFT"] == 0.0
    assert pos.at[pd.Timestamp("2025-09-01"), "SPY"] == 60.0
    assert pos.at[pd.Timestamp("2025-09-02"), "SPY"] == 80.0

    no_cash = PositionHistoryService.get_position_history(PORTFOLIO, end_date=END, include_cash=False)
    assert CASH not in no_cash.columns
    pd.testing.assert_frame_equal(_sorted_cols(no_cash), _sorted_cols(pos.drop(columns=CASH)))

    window = PositionHistoryService.get_position_history(
        PORTFOLIO, start_date="2025-06-01", end_date="2025-12-31"
    )
    assert window.index[0] == pd.Timestamp("2025-06-01")
    assert window.index[-1] == pd.Timestamp("2025-12-31")
    truncated = PositionHistoryService.get_position_history(PORTFOLIO, end_date="2025-06-30")

    delegate = ReturnsDataService.get_position_history(PORTFOLIO, end_date=END)
    pd.testing.assert_frame_equal(_sorted_cols(delegate), _sorted_cols(pos))

    data = {
        "full": {"digest": _digest(pos), "rows": _rows(pos)},
        "no_cash_columns": sorted(no_cash.columns),
        "window_2025H2": {"digest": _digest(window), "rows": _rows(window)},
        "end_2025-06-30": {"digest": _digest(truncated), "last_row": _rows(truncated, ["2025-06-30"])},
        "missing_portfolio_empty": PositionHistoryService.get_position_history("_QT_TEST_missing").empty,
    }
    assert_golden("position_history", data, area=AREA)


def test_position_history_without_end_date_runs_to_today(pf_env):
    before = pd.Timestamp.now().normalize()
    pos = PositionHistoryService.get_position_history(PORTFOLIO)
    after = pd.Timestamp.now().normalize()
    assert pos.index[0] == pd.Timestamp(FIRST_TX)
    assert pos.index[-1] in (before, after)
    tail = pos.loc[pd.Timestamp(END):]
    assert (tail.eq(tail.iloc[0])).all().all()  # no transactions after 2026-06-01


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN-BUG:position-cash-ledger: PositionHistoryService's FREE CASH column counts only "
        "FREE CASH deposits and withdrawals. Security buys and sells never debit or credit it, "
        "unlike the UI ledger in PortfolioService.calculate_free_cash_at_date."
    ),
)
def test_position_history_cash_matches_ui_ledger(pf_env):
    raw = _raw_transactions()
    pos = PositionHistoryService.get_position_history(PORTFOLIO, end_date=END)
    for d in sorted({t["date"] for t in raw}):
        expected = PortfolioService.calculate_free_cash_at_date(raw, d)
        assert pos.at[pd.Timestamp(d), CASH] == pytest.approx(expected), d


def test_daily_weights_golden(pf_env):
    w = PositionHistoryService.get_daily_weights(PORTFOLIO, end_date=END)
    pos = PositionHistoryService.get_position_history(PORTFOLIO, end_date=END)
    assert w.index.equals(pos.index)
    np.testing.assert_allclose(w.sum(axis=1).to_numpy(), 1.0, rtol=1e-12)
    pd.testing.assert_frame_equal(
        _sorted_cols(w), _sorted_cols(_expected_weights(pos)), check_freq=False, rtol=1e-10
    )
    # BTC has no weight until the Saturday it is bought.
    assert w.at[pd.Timestamp("2025-05-09"), "BTC-USD"] == 0.0
    assert w.at[pd.Timestamp("2025-05-10"), "BTC-USD"] > 0.0

    w_nocash = PositionHistoryService.get_daily_weights(PORTFOLIO, end_date=END, include_cash=False)
    assert CASH not in w_nocash.columns
    np.testing.assert_allclose(w_nocash.sum(axis=1).to_numpy(), 1.0, rtol=1e-12)

    delegate = ReturnsDataService.get_daily_weights(PORTFOLIO, end_date=END)
    pd.testing.assert_frame_equal(_sorted_cols(delegate), _sorted_cols(w))

    data = {
        "with_cash": {"digest": _digest(w), "rows": _rows(w)},
        "no_cash": {"digest": _digest(w_nocash), "rows": _rows(w_nocash)},
        "weights_portfolio_empty": PositionHistoryService.get_daily_weights(WEIGHTS_PORTFOLIO).empty,
    }
    assert_golden("daily_weights", data, area=AREA)


# ─────────────────────────────────────────────────────────────────────────────
# Time-varying portfolio returns and resampling
# ─────────────────────────────────────────────────────────────────────────────


def test_time_varying_portfolio_returns_golden(pf_env):
    rds = ReturnsDataService
    # Default arguments (no end_date: weights run to today, then get intersected with the returns calendar).
    daily_cash = rds.get_time_varying_portfolio_returns(PORTFOLIO)
    daily_nocash = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False)

    # BTC-USD trades every day, so the union returns calendar (and the result) covers
    # every calendar day, including weekends before BTC was even bought.
    assert daily_cash.index.equals(pd.date_range(FIRST_TX, END, freq="D"))
    assert daily_nocash.index.equals(daily_cash.index)
    assert daily_cash.name == "portfolio_return"
    assert daily_cash.at[pd.Timestamp("2025-01-04")] == 0.0  # Saturday, no BTC yet -> equities fillna(0)

    w_cash = PositionHistoryService.get_daily_weights(PORTFOLIO, end_date=END, include_cash=True)
    w_nocash = w_cash.drop(columns=CASH)
    w_nocash = w_nocash.div(w_nocash.sum(axis=1), axis=0)  # == get_daily_weights(include_cash=False)
    for series, w in ((daily_cash, w_cash), (daily_nocash, w_nocash)):
        expected = _expected_portfolio_returns(w)
        np.testing.assert_allclose(series.to_numpy(), expected.reindex(series.index).to_numpy(), rtol=1e-10, atol=1e-15)

    # Same-day weights: positions bought on day t earn day t's close-to-close return.
    w0 = w_cash.loc[pd.Timestamp(FIRST_TX)]
    r0 = sum(w0[t] * _close(t).pct_change().loc[pd.Timestamp(FIRST_TX)] for t in ("AAPL", "SPY"))
    assert daily_cash.at[pd.Timestamp(FIRST_TX)] == pytest.approx(r0, rel=1e-12)
    assert daily_cash.at[pd.Timestamp(FIRST_TX)] != 0.0

    window = rds.get_time_varying_portfolio_returns(PORTFOLIO, "2025-03-01", "2025-12-31")
    assert window.index[0] == pd.Timestamp("2025-03-01")
    assert window.index[-1] == pd.Timestamp("2025-12-31")
    np.testing.assert_allclose(window.to_numpy(), daily_cash.loc["2025-03-01":"2025-12-31"].to_numpy(), rtol=1e-12)

    weekly = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False, interval="weekly")
    monthly = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False, interval="monthly")
    yearly = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False, interval="Yearly")
    np.testing.assert_allclose(
        yearly.to_numpy(), ((1 + daily_nocash).resample("YE").prod() - 1).to_numpy(), rtol=1e-10
    )

    w_daily = rds.get_time_varying_portfolio_returns(WEIGHTS_PORTFOLIO, FIRST_TX, END)
    w_monthly = rds.get_time_varying_portfolio_returns(WEIGHTS_PORTFOLIO, FIRST_TX, END, interval="monthly")
    w_rets = pd.DataFrame({t: _close(t).pct_change() for t in ("AAPL", "MSFT", "SPY")}).loc[FIRST_TX:END]
    w_expected = (w_rets.fillna(0.0) * pd.Series({"AAPL": 0.4, "MSFT": 0.25, "SPY": 0.35})).sum(axis=1)
    np.testing.assert_allclose(w_daily.to_numpy(), w_expected.reindex(w_daily.index).to_numpy(), rtol=1e-10)

    sample = ["2025-01-02", "2025-01-03", "2025-01-04", "2025-05-10", "2025-09-02", "2026-06-30"]
    data = {
        "daily_cash": {"digest": _digest(daily_cash), "points": _points(daily_cash, sample)},
        "daily_nocash": {"digest": _digest(daily_nocash), "points": _points(daily_nocash, sample)},
        "window_2025-03_2025-12": _digest(window),
        "weekly_nocash": {"digest": _digest(weekly), "head": weekly.head(3).tolist()},
        "monthly_nocash": {"digest": _digest(monthly), "values": monthly.tolist()},
        "yearly_nocash": {"index": list(yearly.index), "values": yearly.tolist()},
        "weights_portfolio_daily": _digest(w_daily),
        "weights_portfolio_monthly": {"digest": _digest(w_monthly), "values": w_monthly.tolist()},
        "missing_portfolio_empty": rds.get_time_varying_portfolio_returns("_QT_TEST_missing").empty,
    }
    assert_golden("time_varying_returns", data, area=AREA)


def test_monthly_resampling_aligns_across_sources(pf_env):
    """Portfolio, ticker and factor-style monthly series all use month-end ("ME") labels."""
    rds, trs = ReturnsDataService, TickerReturnsService
    daily = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False)
    port_m = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False, interval="monthly")
    spy_d = trs.get_ticker_returns("SPY", "2025-01-01", END)
    spy_m = trs.get_ticker_returns("SPY", "2025-01-01", END, interval="monthly")

    assert port_m.index.is_month_end.all()
    assert port_m.index.equals(spy_m.index)
    assert len(port_m) == 18
    np.testing.assert_allclose(port_m.to_numpy(), ((1 + daily).resample("ME").prod() - 1).to_numpy(), rtol=1e-10)
    np.testing.assert_allclose(spy_m.to_numpy(), ((1 + spy_d).resample("ME").prod() - 1).to_numpy(), rtol=1e-10)

    # Factor data (FactorModels / FactorDataService) is compounded or summed on "ME" too.
    factor_daily = pd.Series(0.0001, index=pd.bdate_range("2025-01-01", END))
    factor_m = factor_daily.resample("ME").sum()
    assert port_m.index.isin(factor_m.index).all()


def _weekly_site(site: str):
    """Return (weekly_series, expected_w_fri_series) for one weekly-resampling code site."""
    rds, trs = ReturnsDataService, TickerReturnsService
    if site == "portfolio":
        daily = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False)
        weekly = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False, interval="weekly")
        return weekly, (1 + daily).resample("W-FRI").prod() - 1
    if site == "ticker":
        daily = trs.get_ticker_returns("SPY", "2025-01-01", END)
        weekly = trs.get_ticker_returns("SPY", "2025-01-01", END, interval="weekly")
        return weekly, (1 + daily).resample("W-FRI").prod() - 1
    if site == "price_bars":
        bars = market_data.fetch_price_history("SPY", period="max", interval="weekly", skip_live_bar=True)
        weekly = bars["Close"].loc["2025-01-01":]
        expected = _close("SPY").resample("W-FRI").last().dropna().loc["2025-01-01":]
        return weekly, expected
    raise AssertionError(site)


@pytest.mark.parametrize("site", ["portfolio", "ticker", "price_bars"])
@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN-BUG:weekly-anchor: ReturnsDataService._resample_returns and market_data._resample_data "
        "resample weekly with 'W' (Sunday labels), but factor data (FactorDataService, "
        "FactorModels, OLS, Frontier) uses 'W-FRI', so weekly series never overlap."
    ),
)
def test_weekly_resampling_is_friday_anchored(pf_env, site):
    weekly, expected = _weekly_site(site)
    assert len(weekly) > 50
    # Desired: Friday labels that line up with the W-FRI factor grid...
    assert (weekly.index.dayofweek == 4).all(), sorted(set(weekly.index.day_name()))
    factor_daily = pd.Series(0.0001, index=pd.bdate_range("2025-01-01", END))
    factor_weekly = factor_daily.resample("W-FRI").sum()
    assert weekly.index.isin(factor_weekly.index).all()
    # ...and the same buckets/values as a W-FRI compounding of the daily data.
    assert weekly.index.equals(expected.index)
    np.testing.assert_allclose(weekly.to_numpy(), expected.to_numpy(), rtol=1e-10)


# ─────────────────────────────────────────────────────────────────────────────
# Cash drag
# ─────────────────────────────────────────────────────────────────────────────


def test_cash_drag_golden(pf_env):
    rds = ReturnsDataService
    full = rds.calculate_cash_drag(PORTFOLIO, end_date=END)
    window = rds.calculate_cash_drag(PORTFOLIO, start_date="2025-03-01", end_date="2025-12-31")
    weights_pf = rds.calculate_cash_drag(WEIGHTS_PORTFOLIO)
    nocash = rds.calculate_cash_drag(NOCASH_PORTFOLIO, end_date=END)

    # The key set depends on the branch; the "no cash column" branch has no cash_drag_annualized.
    assert set(full) == {"avg_cash_weight", "cash_drag_bps", "cash_drag_annualized", "period_days"}
    assert set(nocash) == {"avg_cash_weight", "cash_drag_bps", "period_days"}
    assert weights_pf == {"avg_cash_weight": 0.0, "cash_drag_bps": 0.0, "cash_drag_annualized": 0.0, "period_days": 0}
    assert nocash["avg_cash_weight"] == 0.0 and nocash["period_days"] == 545

    # period_days counts calendar days, and the average cash weight is a calendar-day mean.
    assert full["period_days"] == 545
    assert window["period_days"] == 306
    w = PositionHistoryService.get_daily_weights(PORTFOLIO, end_date=END)
    assert full["avg_cash_weight"] == pytest.approx(w[CASH].mean(), rel=1e-12)
    # Market return = mean over tickers of each ticker's mean daily return over the requested
    # date range. With no start_date that is each ticker's WHOLE price history, not the holding period.
    rets = rds.get_daily_returns(PORTFOLIO, None, END)
    assert rets.index[0] < pd.Timestamp(HISTORY_START) < pd.Timestamp(FIRST_TX)  # BTC CSV back-history
    assert full["cash_drag_bps"] == pytest.approx(full["avg_cash_weight"] * rets.mean().mean() * 252 * 10000, rel=1e-12)
    assert full["cash_drag_annualized"] == pytest.approx(full["cash_drag_bps"] / 10000, rel=1e-12)

    assert_golden(
        "cash_drag",
        {"full": full, "window_2025-03_2025-12": window, "weights_portfolio": weights_pf, "no_cash_portfolio": nocash},
        area=AREA,
    )


def test_cash_drag_without_end_date_counts_days_to_today(pf_env):
    before = pd.Timestamp.now().normalize()
    out = ReturnsDataService.calculate_cash_drag(PORTFOLIO)
    after = pd.Timestamp.now().normalize()
    first = pd.Timestamp(FIRST_TX)
    assert out["period_days"] in ((before - first).days + 1, (after - first).days + 1)


# ─────────────────────────────────────────────────────────────────────────────
# ReturnsDataService rolling metrics (portfolio)
# ─────────────────────────────────────────────────────────────────────────────


def test_rds_rolling_metrics_golden(pf_env):
    rds = ReturnsDataService
    # end_date=END gives the same values as the default (returns end at END anyway) and
    # stops the positions loop from growing with the real clock.
    r = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False)

    vol21 = rds.get_portfolio_volatility(PORTFOLIO, end_date=END)
    vol63 = rds.get_rolling_volatility(PORTFOLIO, 63, end_date=END)
    dd = rds.get_drawdowns(PORTFOLIO, end_date=END)
    rr21 = rds.get_rolling_returns(PORTFOLIO, 21, end_date=END)
    rr63 = rds.get_rolling_returns(PORTFOLIO, 63, end_date=END)
    tuw = rds.get_time_under_water(PORTFOLIO, end_date=END)

    # Vectorized oracles: the P7 rewrite has to keep these equal.
    pd.testing.assert_series_equal(vol21, (r.rolling(21).std() * np.sqrt(252)).dropna(), check_names=False, rtol=1e-12)
    pd.testing.assert_series_equal(vol63, (r.rolling(63).std() * np.sqrt(252)).dropna(), check_names=False, rtol=1e-12)
    cum = (1 + r).cumprod()
    pd.testing.assert_series_equal(dd, cum / cum.cummax() - 1, check_names=False, rtol=1e-12)
    for got, win in ((rr21, 21), (rr63, 63)):
        oracle = np.expm1(np.log1p(r).rolling(win).sum()).dropna()
        assert got.index.equals(oracle.index)
        np.testing.assert_allclose(got.to_numpy(), oracle.to_numpy(), rtol=1e-9, atol=1e-14)
    assert tuw.dtype.kind == "i"
    pd.testing.assert_series_equal(tuw, _time_under_water_vectorized(r), check_names=False)
    assert len(vol21) == len(r) - 20 and len(vol63) == len(r) - 62
    assert (dd <= 0).all() and dd.min() < -0.05
    assert tuw.max() > 0

    dd_cash = rds.get_drawdowns(PORTFOLIO, end_date=END, include_cash=True)
    vol63_cash = rds.get_rolling_volatility(PORTFOLIO, 63, end_date=END, include_cash=True)
    vol21_window = rds.get_rolling_volatility(PORTFOLIO, 21, "2025-06-01", "2025-12-31")
    assert vol21_window.index[0] == pd.Timestamp("2025-06-21")  # 21st row of the window
    # Holding cash dampens both drawdowns and volatility.
    assert dd_cash.min() > dd.min()
    assert vol63_cash.mean() < vol63.mean()

    # Too few observations for the window -> empty Series (not all-NaN).
    assert rds.get_rolling_volatility(PORTFOLIO, 5000, end_date=END).empty
    assert rds.get_rolling_returns(PORTFOLIO, 5000, end_date=END).empty
    assert rds.get_drawdowns("_QT_TEST_missing").empty

    data = {
        "vol21": _digest(vol21), "vol63": _digest(vol63), "drawdowns": _digest(dd),
        "rolling_return_21": _digest(rr21), "rolling_return_63": _digest(rr63),
        "time_under_water": {"digest": _digest(tuw), "max": int(tuw.max()), "last": int(tuw.iloc[-1])},
        "drawdowns_with_cash": _digest(dd_cash), "vol63_with_cash": _digest(vol63_cash),
        "vol21_window_2025H2": _digest(vol21_window),
    }
    assert_golden("rds_rolling_metrics", data, area=AREA)


# ─────────────────────────────────────────────────────────────────────────────
# TickerReturnsService
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ticker", ["SPY", "BTC-USD"])
def test_trs_metrics_golden(pf_env, ticker):
    trs = TickerReturnsService
    daily = trs.get_ticker_returns(ticker, TICKER_START, END)
    oracle = _close(ticker).pct_change().dropna().loc[TICKER_START:END]
    pd.testing.assert_series_equal(daily, oracle, check_names=False, check_freq=False, rtol=1e-12)
    assert daily.name == ticker

    weekly = trs.get_ticker_returns(ticker, TICKER_START, END, interval="weekly")
    monthly = trs.get_ticker_returns(ticker, TICKER_START, END, interval="monthly")
    yearly = trs.get_ticker_returns(ticker, TICKER_START, END, interval="yearly")
    vol21 = trs.get_ticker_volatility(ticker, TICKER_START, END)
    vol63 = trs.get_ticker_rolling_volatility(ticker, 63, TICKER_START, END)
    dd = trs.get_ticker_drawdowns(ticker, TICKER_START, END)
    rr21 = trs.get_ticker_rolling_returns(ticker, 21, TICKER_START, END)
    rr63 = trs.get_ticker_rolling_returns(ticker, 63, TICKER_START, END)
    tuw = trs.get_ticker_time_under_water(ticker, TICKER_START, END)

    pd.testing.assert_series_equal(vol63, (daily.rolling(63).std() * np.sqrt(252)).dropna(), check_names=False, check_freq=False, rtol=1e-12)
    cum = (1 + daily).cumprod()
    pd.testing.assert_series_equal(dd, cum / cum.cummax() - 1, check_names=False, check_freq=False, rtol=1e-12)
    np.testing.assert_allclose(rr63.to_numpy(), np.expm1(np.log1p(daily).rolling(63).sum()).dropna().to_numpy(), rtol=1e-9, atol=1e-14)
    pd.testing.assert_series_equal(tuw, _time_under_water_vectorized(daily), check_names=False, check_freq=False)
    np.testing.assert_allclose(yearly.to_numpy(), ((1 + daily).resample("YE").prod() - 1).to_numpy(), rtol=1e-10)

    assert trs.get_ticker_rolling_volatility(ticker, 10_000, "2026-01-01", END).empty
    assert trs.get_ticker_rolling_returns(ticker, 10_000, "2026-01-01", END).empty

    data = {
        "daily": _digest(daily), "weekly": _digest(weekly),
        "monthly": {"digest": _digest(monthly), "values": monthly.tolist()},
        "yearly": {"index": list(yearly.index), "values": yearly.tolist()},
        "vol21": _digest(vol21), "vol63": _digest(vol63), "drawdowns": _digest(dd),
        "rolling_return_21": _digest(rr21), "rolling_return_63": _digest(rr63),
        "time_under_water": {"digest": _digest(tuw), "max": int(tuw.max()), "last": int(tuw.iloc[-1])},
    }
    assert_golden(f"trs_metrics_{ticker}", data, area=AREA)


def test_trs_btc_full_history_includes_csv_prepend(pf_env):
    full = TickerReturnsService.get_ticker_returns("BTC-USD")
    # Yahoo (fake) history starts at HISTORY_START. market_data prepends the bundled
    # bitcoin_historical_prices.csv (2012-01-01 onward) for every earlier date.
    assert full.index[0] == pd.Timestamp("2012-01-02")
    assert full.index.is_monotonic_increasing and full.index.is_unique
    tail = full.loc[pd.Timestamp(HISTORY_START) + pd.Timedelta(days=1):]
    pd.testing.assert_series_equal(
        tail, _close("BTC-USD").pct_change().loc[tail.index], check_names=False, check_freq=False, rtol=1e-12
    )
    assert_golden("trs_btc_full_history", {"digest": _digest(full)}, area=AREA)


# ─────────────────────────────────────────────────────────────────────────────
# LiveReturnService
# ─────────────────────────────────────────────────────────────────────────────


def _patch_market_open(monkeypatch, is_open: bool):
    from app.utils import market_hours

    monkeypatch.setattr(market_hours, "is_market_open_extended", lambda: is_open)


def _assert_appended_today(out: pd.Series, base: pd.Series, before: pd.Timestamp, after: pd.Timestamp):
    assert len(out) == len(base) + 1
    assert out.index[-1] in (before, after)
    assert out.name == base.name
    np.testing.assert_array_equal(out.iloc[:-1].to_numpy(), base.to_numpy())


def test_live_return_single_ticker(pf_env, live_quotes, monkeypatch):
    trs = TickerReturnsService
    btc = trs.get_ticker_returns("BTC-USD", "2026-01-01", END)
    spy = trs.get_ticker_returns("SPY", "2026-01-01", END)

    _patch_market_open(monkeypatch, False)
    before = pd.Timestamp.now().normalize()
    btc_out = LiveReturnService.append_live_return(btc, "BTC-USD")  # crypto ignores market hours
    spy_closed = LiveReturnService.append_live_return(spy, "SPY")
    _patch_market_open(monkeypatch, True)
    spy_open = LiveReturnService.append_live_return(spy, "SPY")
    after = pd.Timestamp.now().normalize()

    _assert_appended_today(btc_out, btc, before, after)
    _assert_appended_today(spy_open, spy, before, after)
    assert btc_out.iloc[-1] == pytest.approx(live_quotes["BTC-USD"], rel=1e-9)
    assert spy_open.iloc[-1] == pytest.approx(live_quotes["SPY"], rel=1e-9)
    assert spy_closed is spy  # stocks outside extended hours: unchanged, same object

    has_today = pd.concat([spy, pd.Series([0.0], index=[after], name=spy.name)])
    assert LiveReturnService.append_live_return(has_today, "SPY") is has_today
    empty = pd.Series(dtype=float)
    assert LiveReturnService.append_live_return(empty, "SPY") is empty

    assert_golden(
        "live_return_single",
        {"btc": {"appended": btc_out.iloc[-1], "len": len(btc_out)},
         "spy_open": {"appended": spy_open.iloc[-1], "len": len(spy_open)},
         "spy_closed_len": len(spy_closed)},
        area=AREA,
    )


def test_live_portfolio_return(pf_env, live_quotes, monkeypatch):
    rds = ReturnsDataService
    base = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=False)
    base_cash = rds.get_time_varying_portfolio_returns(PORTFOLIO, end_date=END, include_cash=True)

    _patch_market_open(monkeypatch, True)
    before = pd.Timestamp.now().normalize()
    open_nocash = LiveReturnService.append_live_portfolio_return(base, PORTFOLIO, include_cash=False)
    open_cash = LiveReturnService.append_live_portfolio_return(base_cash, PORTFOLIO, include_cash=True)
    _patch_market_open(monkeypatch, False)
    closed = LiveReturnService.append_live_portfolio_return(base, PORTFOLIO, include_cash=False)
    after = pd.Timestamp.now().normalize()

    for out, src in ((open_nocash, base), (open_cash, base_cash), (closed, base)):
        _assert_appended_today(out, src, before, after)

    # Expected: latest-row weights times live returns. The sum is NOT renormalized by the
    # eligible weight, so cash (include_cash=True) and market hours (closed: only crypto) dilute it.
    w_cash = PositionHistoryService.get_daily_weights(PORTFOLIO, end_date=END, include_cash=True).iloc[-1]
    w = w_cash.drop(CASH) / w_cash.drop(CASH).sum()  # == include_cash=False weights
    assert open_nocash.iloc[-1] == pytest.approx(sum(w[t] * live_quotes[t] for t in SECURITIES), rel=1e-9)
    assert open_cash.iloc[-1] == pytest.approx(sum(w_cash[t] * live_quotes[t] for t in SECURITIES), rel=1e-9)
    assert closed.iloc[-1] == pytest.approx(w["BTC-USD"] * live_quotes["BTC-USD"], rel=1e-9)

    empty = pd.Series(dtype=float)
    assert LiveReturnService.append_live_portfolio_return(empty, PORTFOLIO) is empty
    missing = LiveReturnService.append_live_portfolio_return(base, "_QT_TEST_missing")
    assert missing is base

    assert_golden(
        "live_return_portfolio",
        {"open_nocash": open_nocash.iloc[-1], "open_cash": open_cash.iloc[-1],
         "closed_crypto_only": closed.iloc[-1], "len": len(open_nocash)},
        area=AREA,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Known bugs in the returns cache and price policy
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "KNOWN-BUG:returns-cache-stale: ReturnsDataService.get_daily_returns is cached until the "
        "portfolio file changes, so price bars published later are never picked up."
    ),
)
def test_returns_cache_picks_up_new_price_bars(pf_env):
    pf_env.as_of = pd.Timestamp("2026-06-29")
    first = ReturnsDataService.get_daily_returns(PORTFOLIO)
    assert first.index.max() == pd.Timestamp("2026-06-29")
    pf_env.as_of = pd.Timestamp(END)  # a new trading day is published
    second = ReturnsDataService.get_daily_returns(PORTFOLIO)
    assert second.index.max() == pd.Timestamp(END)


@pytest.mark.parametrize("site", ["ticker_returns", "portfolio_daily_returns"])
@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN-BUG:unadjusted-prices: returns come from raw Close. USER DECISION 4 requires "
        "adjusted (total-return) closes everywhere."
    ),
)
def test_returns_use_adjusted_closes(pf_env, site):
    if site == "ticker_returns":
        got = TickerReturnsService.get_ticker_returns("SPY", "2025-01-01", END)
        adj = generate_history("SPY")["Adj Close"]
    else:
        got = ReturnsDataService.get_daily_returns(PORTFOLIO, "2025-01-01", END)["AAPL"].dropna()
        adj = generate_history("AAPL")["Adj Close"]
    expected = adj.pct_change().dropna().loc["2025-01-01":END]
    assert got.index.equals(expected.index)
    np.testing.assert_allclose(got.to_numpy(), expected.to_numpy(), rtol=1e-10, atol=0)
