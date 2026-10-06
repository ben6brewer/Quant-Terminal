"""Characterization: ``app.services.custom_data_service`` persistence + lookup.

Covers save/list/get/delete of a ``_QT_TEST_`` import (including the
case-insensitive de-duplication), storage normalization, interval resampling,
synthesized prices, the ``[Custom]`` prefix helpers and the market_data
intercept.  Every test runs in its own ``fresh_home``.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from app.core.paths import user_data_dir
from app.services import custom_data_service as cds

from ._helpers import CUSTOM_NAME, PREFIX, assert_golden, daily_returns

OTHER_NAME = f"{PREFIX}Monthly"


@pytest.fixture
def cdir(fresh_home):
    root = fresh_home / ".quant_terminal" / "custom_data"
    assert user_data_dir() / "custom_data" == root
    return root


def _save(name=CUSTOM_NAME, returns=None, frequency="daily", asset_class="Equity",
          source="_QT_TEST_source.csv"):
    if returns is None:
        returns = daily_returns()
    return cds.save_custom_import(name, returns, frequency, asset_class, source)


def _monthly_returns():
    idx = pd.date_range("2023-01-31", "2024-06-30", freq="ME")
    rng = np.random.default_rng(11)
    return pd.Series(rng.normal(0.006, 0.03, len(idx)), index=idx)


def _parquets(cdir):
    return sorted(p.name for p in (cdir / "series").glob("*.parquet"))


class TestConstantsAndPrefix:
    def test_public_constants(self):
        assert cds.CUSTOM_PREFIX == "[Custom] "
        assert cds.ASSET_CLASSES == ["Equity", "Fixed Income", "Real Estate", "Commodities",
                                     "Alternatives", "Cash", "Other"]
        assert cds.ALLOWED_FREQUENCIES == ["daily", "weekly", "monthly", "yearly"]
        assert cds.format_custom_ticker(CUSTOM_NAME) == f"[Custom] {CUSTOM_NAME}"

    @pytest.mark.parametrize("text, expected", [
        ("[Custom] X", True), ("[custom] x", True), ("  [CUSTOM] x", True), ("[Custom] ", True),
        ("[Custom]X", False), ("X [Custom] Y", False), ("AAPL", False), ("", False), (None, False),
    ])
    def test_is_custom_ticker(self, text, expected):
        assert cds.is_custom_ticker(text) is expected

    def test_parse_custom_ticker(self, cdir):
        assert cds.parse_custom_ticker(f"[Custom] {CUSTOM_NAME}") is None  # nothing imported yet
        _save()
        for raw in (f"[Custom] {CUSTOM_NAME}", f"[custom]   {CUSTOM_NAME.lower()}  ",
                    f" [CUSTOM] {CUSTOM_NAME.upper()}"):
            assert cds.parse_custom_ticker(raw) == CUSTOM_NAME
        assert cds.parse_custom_ticker("[Custom] ") is None
        assert cds.parse_custom_ticker("[Custom]    ") is None
        assert cds.parse_custom_ticker(CUSTOM_NAME) is None  # no prefix
        assert cds.parse_custom_ticker(f"[Custom] {PREFIX}nope") is None


class TestSaveListGetDelete:
    def test_save_roundtrip(self, cdir):
        returns = daily_returns()
        meta = _save(returns=returns)

        assert isinstance(meta, cds.CustomImportMeta)
        stable = {k: v for k, v in asdict(meta).items() if k != "imported_at"}
        assert stable == {"name": CUSTOM_NAME, "asset_class": "Equity", "frequency": "daily",
                          "start_date": "2024-01-01", "end_date": "2024-06-28",
                          "row_count": len(returns), "source_filename": "_QT_TEST_source.csv"}
        imported_at = datetime.fromisoformat(meta.imported_at)
        assert imported_at.microsecond == 0

        blob = json.loads((cdir / "metadata.json").read_text(encoding="utf-8"))
        assert blob == {"version": 1, "imports": {CUSTOM_NAME: asdict(meta)}}
        assert _parquets(cdir) == [f"{CUSTOM_NAME}.parquet"]
        assert not list(cdir.glob("*.tmp"))

        stored = pd.read_parquet(cdir / "series" / f"{CUSTOM_NAME}.parquet")
        assert list(stored.columns) == ["returns"]
        assert stored.index.name == "date"
        np.testing.assert_array_equal(stored["returns"].to_numpy(), returns.to_numpy())

        assert cds.list_custom_tickers() == [meta]
        assert cds.get_metadata(CUSTOM_NAME.lower()) == meta
        assert cds.get_metadata(f"{PREFIX}nope") is None

        served = cds.get_custom_returns(CUSTOM_NAME)
        assert served.name == f"[Custom] {CUSTOM_NAME}"
        assert served.index.equals(returns.index)
        np.testing.assert_array_equal(served.to_numpy(), returns.to_numpy())
        assert served.dtype == np.float64

    def test_save_normalizes_index_and_duplicates(self, cdir):
        idx = pd.DatetimeIndex(["2024-01-03 15:30", "2024-01-02 09:00", "2024-01-03 10:00",
                                "2024-01-04 00:00"]).tz_localize("America/New_York")
        raw = pd.Series([0.03, 0.02, 0.01, 0.04], index=idx, name="whatever")
        original = raw.copy()
        meta = _save(returns=raw)

        assert raw.equals(original)  # input is not mutated
        assert (meta.start_date, meta.end_date, meta.row_count) == ("2024-01-02", "2024-01-04", 3)
        served = cds.get_custom_returns(CUSTOM_NAME)
        assert list(served.index.strftime("%Y-%m-%d %H:%M")) == [
            "2024-01-02 00:00", "2024-01-03 00:00", "2024-01-04 00:00"]
        assert served.index.tz is None
        # Times are dropped BEFORE sorting, so duplicate dates keep the row that came
        # last in the input (the 10:00 bar), not the latest intraday time.
        assert served.tolist() == [0.02, 0.01, 0.04]

    @pytest.mark.parametrize("kwargs, message", [
        ({"frequency": "Daily"}, "frequency must be one of"),
        ({"frequency": "1d"}, "frequency must be one of"),
        ({"asset_class": "equity"}, "asset_class must be one of"),
        ({"returns": pd.Series([], dtype=float)}, "Cannot save an empty returns series."),
    ])
    def test_save_validation_errors(self, cdir, kwargs, message):
        with pytest.raises(ValueError, match=message):
            _save(**kwargs)
        assert not cdir.exists()  # validation happens before anything is written

    def test_case_insensitive_dedup(self, cdir):
        first = _save(name=f"{PREFIX}series", asset_class="Equity")
        assert first.name == f"{PREFIX}series"
        _save(name=OTHER_NAME, returns=_monthly_returns(), frequency="monthly", asset_class="Other")

        replacement = _monthly_returns() * 2
        second = _save(name=f"{PREFIX}SERIES", returns=replacement, frequency="monthly",
                       asset_class="Fixed Income", source="_QT_TEST_v2.xlsx")

        names = [m.name for m in cds.list_custom_tickers()]
        assert names == [OTHER_NAME, f"{PREFIX}SERIES"]  # sorted case-insensitively ("m" < "s")
        assert len(_parquets(cdir)) == 2  # the old file was replaced, not duplicated
        blob = json.loads((cdir / "metadata.json").read_text(encoding="utf-8"))
        assert sorted(blob["imports"]) == [OTHER_NAME, f"{PREFIX}SERIES"]

        meta = cds.get_metadata(f"{PREFIX}series")
        assert meta == second
        assert (meta.name, meta.frequency, meta.asset_class, meta.source_filename) == (
            f"{PREFIX}SERIES", "monthly", "Fixed Income", "_QT_TEST_v2.xlsx")
        assert cds.parse_custom_ticker(f"[Custom] {PREFIX}Series") == f"{PREFIX}SERIES"
        # Load via the canonical spelling: the parquet path is built from the name
        # as given, so a differently-cased lookup only works on case-insensitive
        # filesystems (Windows/macOS) - callers always pass parse_custom_ticker()'s result.
        served = cds.get_custom_returns(f"{PREFIX}SERIES", "monthly")
        np.testing.assert_allclose(served.to_numpy(), replacement.to_numpy())
        assert served.name == f"[Custom] {PREFIX}SERIES"

    def test_delete_is_case_insensitive(self, cdir):
        _save()
        _save(name=OTHER_NAME, returns=_monthly_returns(), frequency="monthly")
        assert cds.delete_custom_import(CUSTOM_NAME.upper()) is True
        assert _parquets(cdir) == [f"{OTHER_NAME}.parquet"]
        assert [m.name for m in cds.list_custom_tickers()] == [OTHER_NAME]
        assert cds.get_metadata(CUSTOM_NAME) is None
        assert cds.delete_custom_import(CUSTOM_NAME) is False
        with pytest.raises(ValueError, match="Unknown custom ticker"):
            cds.get_custom_returns(CUSTOM_NAME)

        assert cds.delete_custom_import(OTHER_NAME) is True
        blob = json.loads((cdir / "metadata.json").read_text(encoding="utf-8"))
        assert blob == {"version": 1, "imports": {}}
        assert _parquets(cdir) == []

    def test_delete_without_any_imports(self, cdir):
        assert cds.delete_custom_import(CUSTOM_NAME) is False
        assert not (cdir / "metadata.json").exists()

    def test_name_with_path_separators(self, cdir):
        name = f"{PREFIX}a/b\\c"
        _save(name=name)
        assert _parquets(cdir) == [f"{PREFIX}a_b_c.parquet"]
        assert cds.get_metadata(name).name == name
        assert len(cds.get_custom_returns(name)) == len(daily_returns())

    def test_missing_parquet_and_corrupt_metadata(self, cdir):
        _save()
        (cdir / "series" / f"{CUSTOM_NAME}.parquet").unlink()
        with pytest.raises(ValueError, match="has no stored data"):
            cds.get_custom_returns(CUSTOM_NAME)

        for text in ("{broken", "[1, 2]", json.dumps({"imports": []}), json.dumps({"version": 1})):
            (cdir / "metadata.json").write_text(text, encoding="utf-8")
            assert cds.list_custom_tickers() == []
            assert cds.get_metadata(CUSTOM_NAME) is None
            assert cds.parse_custom_ticker(f"[Custom] {CUSTOM_NAME}") is None

        # Entries with missing fields are skipped by list and unreadable by get.
        (cdir / "metadata.json").write_text(json.dumps(
            {"version": 1, "imports": {CUSTOM_NAME: {"name": CUSTOM_NAME}}}), encoding="utf-8")
        assert cds.list_custom_tickers() == []
        assert cds.get_metadata(CUSTOM_NAME) is None
        assert cds.parse_custom_ticker(f"[Custom] {CUSTOM_NAME}") == CUSTOM_NAME


class TestIntervalsAndPrices:
    def test_resampling_from_daily(self, cdir):
        returns = daily_returns()
        _save(returns=returns)
        out = {iv: cds.get_custom_returns(CUSTOM_NAME, iv) for iv in ("daily", "weekly", "monthly", "yearly")}

        assert (out["weekly"].index.dayofweek == 6).all()  # pandas "W" == W-SUN
        assert out["monthly"].index.is_month_end.all()
        assert list(out["yearly"].index.strftime("%Y-%m-%d")) == ["2024-12-31"]
        jan = returns[returns.index.month == 1]
        assert out["monthly"].iloc[0] == pytest.approx((1 + jan).prod() - 1)
        assert out["yearly"].iloc[0] == pytest.approx((1 + returns).prod() - 1)
        assert all(s.name == f"[Custom] {CUSTOM_NAME}" for s in out.values())

        assert_golden("custom_returns_by_interval", out, area="custom_data")

    @pytest.mark.parametrize("alias, canonical", [
        ("1d", "daily"), ("d", "daily"), (" Daily ", "daily"), ("", "daily"), (None, "daily"),
        ("5min", "daily"), ("1wk", "weekly"), ("w", "weekly"), ("1mo", "monthly"), ("m", "monthly"),
        ("me", "monthly"), ("MONTHLY", "monthly"), ("1y", "yearly"), ("y", "yearly"), ("ye", "yearly"),
    ])
    def test_interval_aliases(self, cdir, alias, canonical):
        _save()
        pd.testing.assert_series_equal(cds.get_custom_returns(CUSTOM_NAME, alias),
                                       cds.get_custom_returns(CUSTOM_NAME, canonical))

    def test_finer_interval_than_stored_is_rejected(self, cdir):
        monthly = _monthly_returns()
        _save(name=OTHER_NAME, returns=monthly, frequency="monthly")
        for iv in ("daily", "weekly", "1d", "1wk"):
            with pytest.raises(ValueError, match=r"was imported at monthly frequency; cannot serve "
                                                 r"(daily|weekly) data \(which is finer\)"):
                cds.get_custom_returns(OTHER_NAME, iv)
        # Same frequency -> served as stored (no resample); coarser -> compounded.
        served = cds.get_custom_returns(OTHER_NAME, "monthly")
        np.testing.assert_allclose(served.to_numpy(), monthly.to_numpy())
        yearly = cds.get_custom_returns(OTHER_NAME, "yearly")
        assert list(yearly.index.year) == [2023, 2024]
        assert yearly.iloc[0] == pytest.approx((1 + monthly[monthly.index.year == 2023]).prod() - 1)

    def test_weekly_import_served_as_stored(self, cdir):
        idx = pd.date_range("2024-01-05", periods=10, freq="W-FRI")
        weekly = pd.Series(np.linspace(-0.02, 0.03, 10), index=idx)
        _save(returns=weekly, frequency="weekly")
        served = cds.get_custom_returns(CUSTOM_NAME, "weekly")
        assert (served.index.dayofweek == 4).all()  # not re-anchored to W-SUN
        np.testing.assert_allclose(served.to_numpy(), weekly.to_numpy())

    def test_custom_prices(self, cdir):
        returns = daily_returns()
        _save(returns=returns)
        prices = cds.get_custom_prices(CUSTOM_NAME)
        assert list(prices.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert prices.index.name is None
        assert prices.index.equals(returns.index)
        np.testing.assert_allclose(prices["Close"].to_numpy(), (100.0 * (1 + returns).cumprod()).to_numpy())
        for col in ("Open", "High", "Low"):
            np.testing.assert_array_equal(prices[col].to_numpy(), prices["Close"].to_numpy())
        assert (prices["Volume"] == 0).all()

        monthly_prices = cds.get_custom_prices(CUSTOM_NAME, "monthly")
        assert len(monthly_prices) == 6
        assert monthly_prices["Close"].iloc[-1] == pytest.approx(prices["Close"].iloc[-1])

        assert_golden("custom_prices", {"daily": prices, "monthly": monthly_prices}, area="custom_data")

    def test_end_dates_and_coarsest_frequency(self, cdir):
        _save()  # daily, ends 2024-06-28
        _save(name=OTHER_NAME, returns=_monthly_returns(), frequency="monthly")  # ends 2024-06-30
        tickers = ["AAPL", f"[custom] {CUSTOM_NAME.lower()}", f"[Custom] {OTHER_NAME}",
                   f"[Custom] {PREFIX}missing", "FREE CASH"]
        assert cds.custom_end_dates(tickers) == {
            f"[custom] {CUSTOM_NAME.lower()}": "2024-06-28", f"[Custom] {OTHER_NAME}": "2024-06-30"}
        assert cds.coarsest_custom_frequency(tickers) == "monthly"
        assert cds.coarsest_custom_frequency(tickers[:2]) == "daily"
        assert cds.coarsest_custom_frequency(["AAPL", f"[Custom] {PREFIX}missing"]) is None
        assert cds.custom_end_dates([]) == {}


class TestMarketDataIntercept:
    def test_fetch_price_history_serves_custom_prices(self, market_env, cdir):
        from app.services.market_data import fetch_price_history

        _save()
        df = fetch_price_history(f"  [custom] {CUSTOM_NAME.upper()}")
        pd.testing.assert_frame_equal(df, cds.get_custom_prices(CUSTOM_NAME))
        weekly = fetch_price_history(f"[Custom] {CUSTOM_NAME}", period="1y", interval="Weekly")
        pd.testing.assert_frame_equal(weekly, cds.get_custom_prices(CUSTOM_NAME, "weekly"))
        assert market_env.calls == []  # never reaches Yahoo
        assert not (cdir.parent / "cache" / f"[Custom] {CUSTOM_NAME}.parquet").exists()

        with pytest.raises(ValueError, match="Unknown custom ticker"):
            fetch_price_history(f"[Custom] {PREFIX}missing")
        assert market_env.calls == []
