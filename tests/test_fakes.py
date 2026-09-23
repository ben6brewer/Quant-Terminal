"""Tests for the offline fakes in tests/fixtures (FakeFred, FakeYahoo)."""

import importlib
import pkgutil

import numpy as np
import pandas as pd
import pytest

from fixtures import fake_fred as ff
from fixtures import fake_yahoo as fy

END = pd.Timestamp("2026-06-30")


# ── FakeFred ─────────────────────────────────────────────────────────────────


def _all_fred_service_classes():
    """Import every FRED service module under app and return BaseFredService subclasses."""
    import app
    from app.services.base_fred_service import BaseFredService

    for info in pkgutil.walk_packages(app.__path__, "app.", onerror=lambda _name: None):
        name = info.name
        leaf = name.rsplit(".", 1)[-1]
        if "fred" in leaf or (".services." in name and leaf.endswith("_service")):
            try:
                importlib.import_module(name)
            except Exception:  # pragma: no cover - reported by import tests elsewhere
                continue
    out, stack = [], list(BaseFredService.__subclasses__())
    while stack:
        cls = stack.pop()
        out.append(cls)
        stack.extend(cls.__subclasses__())
    return sorted(set(out), key=lambda c: c.__qualname__)


class TestFakeFredData:
    def test_every_json_series_native_frequency_and_end(self):
        freqs = ff.load_frequencies()
        assert len(freqs) > 200
        last_expected = {"D": END, "M": pd.Timestamp("2026-06-01"), "Q": pd.Timestamp("2026-04-01"),
                         "A": pd.Timestamp("2026-01-01")}
        for sid, f in freqs.items():
            assert f in "DWMQA", sid
            s = ff.generate_series(sid)
            idx = s.index
            assert len(s) > 5 and s.dtype == "float64", sid
            assert idx.is_monotonic_increasing and idx.is_unique, sid
            assert idx[-1] <= END, sid
            if f == "D":
                if sid not in ff.CALENDAR_DAILY:
                    assert (idx.dayofweek < 5).all(), sid
            elif f == "W":
                assert idx.dayofweek.nunique() == 1 and (np.diff(idx.values).astype("timedelta64[D]").astype(int) == 7).all(), sid
                assert idx[-1] > END - pd.Timedelta(days=7), sid
            elif f == "M":
                assert (idx.day == 1).all(), sid
            elif f == "Q":
                assert (idx.day == 1).all() and set(idx.month) <= {1, 4, 7, 10}, sid
            else:
                assert ((idx.day == 1) & (idx.month == 1)).all(), sid
            if f != "W":
                assert idx[-1] == last_expected[f], sid

    def test_deterministic_and_distinct(self):
        a = ff.generate_series("UNRATE")
        b = ff.FakeFredController().series("UNRATE")
        pd.testing.assert_series_equal(a, b)
        assert not np.allclose(ff.generate_series("DGS10").tail(50), ff.generate_series("DGS2").tail(50))

    def test_realistic_magnitudes(self):
        assert 1 < ff.generate_series("UNRATE").mean() < 12
        assert ff.generate_series("PAYEMS").iloc[-1] == pytest.approx(159500)
        assert 200 < ff.generate_series("CPIAUCSL").iloc[-1] < 400
        assert ff.generate_series("DGS10").min() >= 0.3

    def test_usrec_spans(self):
        s = ff.generate_series("USREC")
        assert set(s.unique()) == {0.0, 1.0}
        assert s["2008-06-01"] == 1.0 and s["2020-03-01"] == 1.0
        assert s["2015-06-01"] == 0.0 and s.iloc[-1] == 0.0

    def test_daily_holidays_are_nan(self):
        s = ff.generate_series("DGS10")
        assert np.isnan(s["2025-12-25"]) and not np.isnan(s["2025-12-24"])

    def test_fed_target_range(self):
        lo, hi = ff.generate_series("DFEDTARL"), ff.generate_series("DFEDTARU")
        assert ((hi - lo).round(6) == 0.25).all()
        assert (lo.index == pd.date_range("2008-12-16", END, freq="D")).all()
        assert ((lo * 4) % 1 == 0).all() and lo.min() >= 0


class TestFakeFredApi:
    def test_get_series_slices_consistently(self):
        cls, ctl = ff.make_fake_fred_class()
        fred = cls(api_key="_QT_TEST")
        full = fred.get_series("UNRATE")
        part = fred.get_series("UNRATE", observation_start="2020-01-01", observation_end="2021-01-01")
        pd.testing.assert_series_equal(part, full["2020-01-01":"2021-01-01"])
        assert ctl.calls == [("UNRATE", None, None), ("UNRATE", "2020-01-01", "2021-01-01")]
        assert ctl.instances == 1

    def test_errors(self):
        cls, ctl = ff.make_fake_fred_class()
        with pytest.raises(ValueError, match="API key"):
            cls()
        fred = cls(api_key="_QT_TEST")
        with pytest.raises(ValueError, match="does not exist"):
            fred.get_series("_QT_TEST_NOT_A_SERIES")
        ctl.fail.add("GDP")
        with pytest.raises(ValueError):
            fred.get_series("GDP")
        with pytest.raises(NotImplementedError):
            fred.get_series("GDP", frequency="a")

    def test_end_dates_and_overrides(self):
        cls, ctl = ff.make_fake_fred_class()
        fred = cls(api_key="_QT_TEST")
        ctl.end_dates["PAYEMS"] = "2026-03-01"
        assert fred.get_series("PAYEMS").index[-1] == pd.Timestamp("2026-03-01")
        custom = pd.Series([1.0, 2.0], index=pd.to_datetime(["2020-01-01", "2020-02-01"]))
        ctl.overrides["USREC"] = custom
        pd.testing.assert_series_equal(fred.get_series("USREC", observation_start="2020-02-01"), custom.iloc[1:])

    def test_series_info(self):
        cls, _ = ff.make_fake_fred_class()
        info = cls(api_key="_QT_TEST").get_series_info("GNPCA")
        assert info["frequency_short"] == "A" and info["id"] == "GNPCA"

    def test_patch_fred_fixture(self, fake_fred):
        import fredapi
        import fredapi.fred
        from fredapi import Fred

        assert fredapi.fred.Fred is fredapi.Fred is Fred
        s = Fred(api_key="_QT_TEST").get_series("GDP", observation_start="2025-01-01")
        assert list(s.index) == list(pd.date_range("2025-01-01", "2026-04-01", freq="QS-JAN"))
        assert fake_fred.call_ids() == ["GDP"]


class TestFakeFredAgainstServices:
    def test_every_requested_series_is_known(self, fake_fred, fake_yahoo, fresh_home):
        """Run every FRED service with FakeFred: all requested ids must be in the JSON."""
        import app.services.base_fred_service as base

        base._version_checked = False
        services = _all_fred_service_classes()
        assert len(services) >= 30
        for svc in services:
            if svc.GROUPS or "fetch_all_data" in vars(svc):
                result = svc.fetch_all_data()
                assert result, svc.__name__
                for key, df in result.items():
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        assert df.index.max() <= END, (svc.__name__, key)
        from app.ui.modules.treasury.services.treasury_fred_service import TreasuryFredService

        assert TreasuryFredService.fetch_all_treasury_data() is not None
        unknown = sorted(set(fake_fred.call_ids()) - set(fake_fred.frequencies))
        assert unknown == []
        assert len(set(fake_fred.call_ids())) > 200


# ── FakeYahoo ────────────────────────────────────────────────────────────────


class TestFakeYahooData:
    def test_deterministic(self):
        pd.testing.assert_frame_equal(fy.generate_history("AAPL"), fy.generate_history("aapl"))
        assert not fy.generate_history("AAPL")["Close"].equals(fy.generate_history("MSFT")["Close"])

    def test_calendars(self):
        eq = fy.generate_history("SPY")
        assert (eq.index.dayofweek < 5).all() and eq.index[-1] == END
        assert pd.Timestamp("2025-12-25") not in eq.index
        btc = fy.generate_history("BTC-USD")
        assert (btc.index.dayofweek >= 5).any() and btc.index[0] == pd.Timestamp("2014-09-17")

    def test_adjusted_close_dividend_drift(self):
        eq = fy.generate_history("SPY")
        assert (eq["Adj Close"] <= eq["Close"] + 1e-9).all()
        assert eq["Adj Close"].iloc[0] < eq["Close"].iloc[0]
        ratio = (eq["Adj Close"] / eq["Close"]).iloc[0]
        assert 0.3 < ratio < 1.0
        idx = fy.generate_history("^GSPC")
        pd.testing.assert_series_equal(idx["Adj Close"], idx["Close"], check_names=False)

    def test_ohlc_consistency(self):
        df = fy.generate_history("AAPL")
        assert (df["High"] >= df[["Open", "Close"]].max(axis=1) - 1e-9).all()
        assert (df["Low"] <= df[["Open", "Close"]].min(axis=1) + 1e-9).all()
        assert df["Volume"].dtype == "int64" and (df["Volume"] > 0).all()

    def test_special_levels(self):
        assert 0 < fy.generate_history("^IRX")["Close"].iloc[-1] < 10
        assert 94 <= fy.generate_history("ZQN26.CBT")["Close"].iloc[-1] <= 100
        assert fy.generate_history("GC=F")["Close"].iloc[-1] == pytest.approx(2400)


class TestFakeYahooDownload:
    def test_start_inclusive_end_exclusive(self):
        ctl = fy.FakeYahooController()
        df = ctl.download("AAPL", start="2026-06-01", end="2026-06-05", auto_adjust=False)
        assert list(df.index) == list(pd.bdate_range("2026-06-01", "2026-06-04"))
        assert df.index.name == "Date"

    def test_periods(self):
        ctl = fy.FakeYahooController()
        assert len(ctl.download("AAPL", period="5d")) == 5
        one_mo = ctl.download("AAPL")  # default period 1mo
        assert one_mo.index[0] >= END - pd.DateOffset(months=1)
        assert len(ctl.download("AAPL", period="max")) == len(fy.generate_history("AAPL"))
        assert ctl.download("AAPL", period="ytd").index[0].year == 2026

    def test_layouts(self):
        ctl = fy.FakeYahooController()
        single = ctl.download("AAPL", period="5d", auto_adjust=False)
        assert list(single.columns) == [(f, "AAPL") for f in fy.PRICE_FIELDS_RAW]
        assert single.columns.names == ["Price", "Ticker"]
        flat = ctl.download("AAPL", period="5d", multi_level_index=False)
        assert list(flat.columns) == fy.PRICE_FIELDS_ADJ
        multi = ctl.download("MSFT AAPL", period="5d", auto_adjust=False)
        assert multi.columns.get_level_values("Ticker").unique().tolist() == ["AAPL", "MSFT"]
        by_ticker = ctl.download(["MSFT", "AAPL"], period="5d", group_by="ticker", auto_adjust=False)
        assert by_ticker.columns.names == ["Ticker", "Price"]
        assert list(by_ticker["AAPL"].columns) == ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

    def test_auto_adjust(self):
        ctl = fy.FakeYahooController()
        raw = ctl.download("SPY", start="2000-01-01", end="2000-02-01", auto_adjust=False)
        adj = ctl.download("SPY", start="2000-01-01", end="2000-02-01")
        assert len(raw) == len(adj) > 15
        assert "Adj Close" not in adj.columns.get_level_values("Price")
        np.testing.assert_allclose(adj[("Close", "SPY")], raw[("Adj Close", "SPY")])
        assert (adj[("Close", "SPY")] < raw[("Close", "SPY")]).all()

    def test_missing_and_failing_tickers(self):
        ctl = fy.FakeYahooController()
        ctl.missing.add("_QT_TEST_BAD")
        assert ctl.download("_QT_TEST_BAD", period="5d").empty
        both = ctl.download(["AAPL", "_QT_TEST_BAD"], period="5d")
        assert both[("Close", "_QT_TEST_BAD")].isna().all() and both[("Close", "AAPL")].notna().all()
        ctl.fail.add("_QT_TEST_BOOM")
        with pytest.raises(RuntimeError):
            ctl.download(["AAPL", "_QT_TEST_BOOM"])
        assert [c["tickers"] for c in ctl.calls][-1] == ["AAPL", "_QT_TEST_BOOM"]

    def test_weekly_interval(self):
        ctl = fy.FakeYahooController()
        wk = ctl.download("AAPL", period="3mo", interval="1wk", multi_level_index=False)
        assert (wk.index.dayofweek == 4).all()
        with pytest.raises(NotImplementedError):
            ctl.download("AAPL", period="5d", interval="1m")

    def test_ticker_info(self):
        ctl = fy.FakeYahooController()
        info = ctl.ticker_info("AAPL")
        for key in ("sector", "industry", "quoteType", "marketCap", "beta", "country", "currency",
                    "shortName", "regularMarketPrice"):
            assert info.get(key) is not None, key
        assert ctl.ticker_info("^GSPC")["quoteType"] == "INDEX"
        ctl.missing.add("_QT_TEST_BAD")
        assert ctl.ticker_info("_QT_TEST_BAD") == {"trailingPegRatio": None}


class TestFakeYahooPatch:
    def test_service_paths(self, fake_yahoo, fresh_home):
        from app.services.yahoo_finance_service import YahooFinanceService as Y

        full = Y.fetch_full_history("AAPL")
        assert list(full.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert full.index[-1] == END
        prices = Y.fetch_batch_current_prices(["AAPL", "SPY"])
        assert set(prices) == {"AAPL", "SPY"}
        fake_yahoo.missing.add("_QT_TEST_BAD")
        assert Y.is_valid_ticker("AAPL") and not Y.is_valid_ticker("_QT_TEST_BAD")
        assert fake_yahoo.calls[0]["tickers"] == ["AAPL"] and fake_yahoo.calls[0]["period"] == "max"

    def test_yfinance_module_patched(self, fake_yahoo):
        import yfinance as yf

        assert yf.download("AAPL", period="5d").shape[0] == 5
        assert yf.Ticker("AAPL").info["symbol"] == "AAPL"
