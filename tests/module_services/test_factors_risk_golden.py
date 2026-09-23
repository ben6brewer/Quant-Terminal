"""Characterization goldens for factor data, factor regressions and risk analytics [P0.T6].

Pins the CURRENT behaviour of

* ``app.services.ken_french_loader`` (Ken French zip download + CSV parsing),
* ``FactorDataService`` (factor_models; FF / q-factor / AQR / custom sources,
  daily / weekly / monthly, same-day cache),
* ``FamaFrenchDataService`` (risk_analytics; 30-day cache),
* ``FactorModelService`` vs the ``OLSRegressionService._run_ols`` kernel
  (including the adjusted-R^2 off-by-one, KNOWN-BUG:adj-r2),
* ``FactorRegressionService`` (factor_models regressions on FactorDataService data),
* ``FactorRiskService`` contribution / CTEV methods and
* ``RiskAnalyticsService`` on a small ``_QT_TEST_`` fixture portfolio,

before P8 folds them into one Fama-French source, one OLS kernel and a
RiskDataLoader.  Inputs are offline and deterministic:

* ``tests/fixtures/ff/*.csv``: small synthetic Ken French / q-factor / AQR
  tables (see ``generate_ff_fixtures.py`` there).  :class:`FakeFactorWeb`
  serves them at the real download URLs by patching ``urlopen`` (the
  loader's and ``urllib.request``'s, which pandas uses), so the whole
  download -> unzip -> parse -> clean -> cache path runs for real.
* Security prices come from FakeYahoo: each ``_QT_TEST_*`` ticker's return is
  ``RF + factors @ betas + idio * (FakeYahoo generated return)``, served
  through ``fake_yahoo.overrides`` and read back with ``fake_yahoo.download``.

Every test runs in ``fresh_home`` with the services' in-memory caches reset.
Regenerate goldens only in a Behavior-Change commit (``--update-goldens``).
"""

from __future__ import annotations

import functools
import io
import math
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import numpy as np
import pandas as pd
import pytest

import app.services.ken_french_loader as kfl
from app.services.ticker_metadata_service import TickerMetadataService
from app.ui.modules.analysis.services.ols_regression_service import OLSRegressionService
from app.ui.modules.factor_models.services.factor_data_service import FactorDataService
from app.ui.modules.factor_models.services.factor_regression_service import (
    FactorRegressionService,
)
from app.ui.modules.factor_models.services.model_definitions import MODELS, FactorModelSpec
from app.ui.modules.risk_analytics.services.factor_model_service import FactorModelService
from app.ui.modules.risk_analytics.services.factor_risk_service import FactorRiskService
from app.ui.modules.risk_analytics.services.risk_analytics_service import RiskAnalyticsService
from app.ui.modules.risk_analytics.services.sector_override_service import (
    SectorOverrideService,
)
from fixtures.fake_yahoo import generate_history
from golden_utils import assert_golden, frame_digest

pytestmark = pytest.mark.golden

AREA = "factors_risk"
FF_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ff"

# ─────────────────────────────────────────────────────────────────────────────
# Fake internet for the factor downloads
# ─────────────────────────────────────────────────────────────────────────────

KF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
KF_FF5_DAILY = "F-F_Research_Data_5_Factors_2x3_daily"
KF_MOM_DAILY = "F-F_Momentum_Factor_daily"
KF_FF5_MONTHLY = "F-F_Research_Data_5_Factors_2x3"
KF_MOM_MONTHLY = "F-F_Momentum_Factor"
KF_DATASETS = (KF_FF5_DAILY, KF_MOM_DAILY, KF_FF5_MONTHLY, KF_MOM_MONTHLY)

Q_BASE = "http://global-q.org/uploads/1/2/2/6/122679606/"
Q_FILES = ("q5_factors_daily_2023.csv", "q5_factors_monthly_2023.csv")

AQR_BASE = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"
# url file -> (fixture csv, sheet names; the LAST sheet holds the data)
AQR_FILES = {
    "Betting-Against-Beta-Equity-Factors-Monthly.xlsx": ("aqr_bab_monthly.csv", ("_QT_TEST_Info", "USA")),
    # no sheet contains "usa" -> the service falls back to the first sheet
    "Quality-Minus-Junk-Factors-Monthly.xlsx": ("aqr_qmj_monthly.csv", ("QMJ Factors",)),
    "The-Devil-in-HMLs-Details-Factors-Monthly.xlsx": ("aqr_hml_devil_monthly.csv", ("_QT_TEST_Readme", "USA")),
}


def kf_url(dataset: str) -> str:
    return f"{KF_BASE}{dataset}_CSV.zip"


def _zip_bytes(member: str, payload: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, payload)
    return buf.getvalue()


@functools.lru_cache(maxsize=None)
def _kf_zip(dataset: str) -> bytes:
    # Real Ken French zips hold a single upper-case ``<name>.CSV`` member.
    return _zip_bytes(f"{dataset}.CSV", (FF_DIR / f"{dataset}.csv").read_bytes())


@functools.lru_cache(maxsize=None)
def _aqr_xlsx(csv_name: str, sheets: tuple) -> bytes:
    data = pd.read_csv(FF_DIR / csv_name, parse_dates=["DATE"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for sheet in sheets[:-1]:
            pd.DataFrame({"note": ["_QT_TEST_ synthetic workbook"]}).to_excel(xw, sheet_name=sheet, index=False)
        data.to_excel(xw, sheet_name=sheets[-1], index=False)
    return buf.getvalue()


class _FakeHTTPResponse(io.BytesIO):
    """Just enough of ``http.client.HTTPResponse`` for the loader and pandas."""

    def __init__(self, payload: bytes, url: str):
        super().__init__(payload)
        self.url = url
        self.status = 200
        self.headers = {}

    def geturl(self) -> str:
        return self.url


class FakeFactorWeb:
    """Serves fixture bytes at the factor-download URLs; records every request.

    ``requests``: list of ``{"url", "user_agent", "timeout"}``.  ``fail``: URLs
    that raise ``URLError`` (simulated outage).  Unknown URLs raise too.
    """

    def __init__(self):
        self.routes: dict = {}
        self.requests: list = []
        self.fail: set = set()

    def install_defaults(self) -> "FakeFactorWeb":
        for ds in KF_DATASETS:
            self.routes[kf_url(ds)] = _kf_zip(ds)
        for name in Q_FILES:
            self.routes[Q_BASE + name] = (FF_DIR / name).read_bytes()
        for name, (csv_name, sheets) in AQR_FILES.items():
            self.routes[AQR_BASE + name] = _aqr_xlsx(csv_name, sheets)
        return self

    def serve_kf_text(self, dataset: str, text: str, member: Optional[str] = None) -> None:
        self.routes[kf_url(dataset)] = _zip_bytes(member or f"{dataset}.CSV", text.encode("latin-1"))

    def urlopen(self, req, data=None, timeout=None, **_kw):
        if isinstance(req, urllib.request.Request):
            url, agent = req.full_url, req.get_header("User-agent")
        else:
            url, agent = str(req), None
        self.requests.append({"url": url, "user_agent": agent, "timeout": timeout})
        if url in self.fail:
            raise urllib.error.URLError("_QT_TEST_ simulated outage")
        if url not in self.routes:
            raise urllib.error.URLError(f"_QT_TEST_ FakeFactorWeb has no route for {url}")
        return _FakeHTTPResponse(self.routes[url], url)

    def urls(self) -> list:
        """Requested URLs, shortened to the file name, in request order."""
        return [r["url"].rsplit("/", 1)[-1] for r in self.requests]


@pytest.fixture
def factor_web(monkeypatch) -> FakeFactorWeb:
    web = FakeFactorWeb().install_defaults()
    monkeypatch.setattr(kfl, "urlopen", web.urlopen, raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", web.urlopen)
    return web


def _fama_french_service():
    """FamaFrenchDataService, or None once P8 deletes it (single Fama-French source)."""
    try:
        from app.ui.modules.risk_analytics.services.fama_french_data_service import (
            FamaFrenchDataService,
        )
    except ImportError:
        return None
    return FamaFrenchDataService


@pytest.fixture
def isolated_state(fresh_home, monkeypatch) -> Path:
    """Own home directory plus empty in-memory caches of every service used here."""
    monkeypatch.setattr(FactorDataService, "_memory", {})
    monkeypatch.setattr(TickerMetadataService, "_cache", None)
    monkeypatch.setattr(SectorOverrideService, "_overrides", None)
    ffs = _fama_french_service()
    if ffs is not None:
        monkeypatch.setattr(ffs, "_cached_data", None)
    return fresh_home


@pytest.fixture
def factor_env(isolated_state, factor_web) -> SimpleNamespace:
    return SimpleNamespace(home=isolated_state, web=factor_web)


# ─────────────────────────────────────────────────────────────────────────────
# Test-side fixture reading (independent of the product parser)
# ─────────────────────────────────────────────────────────────────────────────

FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]


def _kf_table(dataset: str) -> pd.DataFrame:
    """First table of a Ken French fixture file, in PERCENT."""
    lines = (FF_DIR / f"{dataset}.csv").read_text(encoding="latin-1").splitlines()
    head = next(i for i, line in enumerate(lines) if line.startswith(","))
    cols = [c.strip() for c in lines[head].split(",")[1:]]
    dates, rows = [], []
    for line in lines[head + 1:]:
        if not line.strip():
            break
        cells = [c.strip() for c in line.split(",")]
        dates.append(cells[0])
        rows.append([float(c) for c in cells[1:]])
    fmt = "%Y%m%d" if len(dates[0]) == 8 else "%Y%m"
    return pd.DataFrame(rows, index=pd.to_datetime(dates, format=fmt), columns=cols)


@functools.lru_cache(maxsize=None)
def _ff_decimal_cached(freq: str) -> pd.DataFrame:
    ff5 = _kf_table(KF_FF5_DAILY if freq == "daily" else KF_FF5_MONTHLY)
    mom = _kf_table(KF_MOM_DAILY if freq == "daily" else KF_MOM_MONTHLY).rename(columns={"Mom": "UMD"})
    return ff5.join(mom, how="inner") / 100.0


def ff_decimal(freq: str) -> pd.DataFrame:
    """Fixture FF5 + UMD + RF (decimals) joined on common dates ("daily"/"monthly")."""
    return _ff_decimal_cached(freq).copy()


# ─────────────────────────────────────────────────────────────────────────────
# Fixture portfolio (FakeYahoo prices with a known factor structure)
# ─────────────────────────────────────────────────────────────────────────────

PRICE_START = "2024-12-02"  # first FakeYahoo bar used for the fixture prices
RISK_START = "2025-06-02"  # the analysed window (~ a 1Y lookback ending 2026-06-30)


@dataclass(frozen=True)
class _Sec:
    port: float  # portfolio weight
    bench: float  # benchmark weight
    betas: tuple  # true loadings on FACTORS
    idio: float  # scale of the FakeYahoo idiosyncratic return
    sector: str
    industry: Optional[str]
    country: str
    currency: str
    beta: Optional[float]  # Yahoo "beta" (ex-ante beta input)


# Active weights (+.15, +.18, +.12, +.10, -.35, -.20) and sector / industry
# totals are all distinct so every sorted output has a deterministic order.
UNIVERSE = {
    "_QT_TEST_ALPHA": _Sec(0.40, 0.25, (1.25, -0.20, -0.40, 0.30, -0.10, 0.20), 0.5,
                           "Technology", "Software - Infrastructure", "United States", "USD", 1.3),
    "_QT_TEST_BRAVO": _Sec(0.30, 0.12, (0.90, 0.10, 0.80, 0.20, 0.30, -0.10), 0.5,
                           "Financial Services", "Banks - Diversified", "United States", "USD", 1.1),
    "_QT_TEST_CHARLIE": _Sec(0.20, 0.08, (1.10, 0.40, 0.50, -0.20, 0.60, 0.00), 0.6,
                             "Energy", "Oil & Gas Integrated", "United States", "USD", 0.95),
    "_QT_TEST_DELTA": _Sec(0.10, 0.00, (0.60, -0.30, 0.10, 0.50, 0.20, 0.05), 0.4,
                           "Healthcare", "Drug Manufacturers - General", "Netherlands", "EUR", None),
    "_QT_TEST_ECHO": _Sec(0.00, 0.35, (1.00, -0.10, -0.30, 0.10, -0.20, 0.30), 0.5,
                          "Communication Services", "Internet Content & Information", "United States", "USD", 1.05),
    "_QT_TEST_FOXTROT": _Sec(0.00, 0.20, (0.80, 0.60, 0.20, -0.10, 0.10, -0.20), 0.7,
                             "Technology", None, "United States", "USD", None),
}
SECTOR_OVERRIDE = ("_QT_TEST_CHARLIE", "Utilities")
HOLDING_LOCATION = {"_QT_TEST_ECHO": "Ireland"}  # iShares location wins over metadata country


@dataclass(frozen=True)
class _Holding:
    """Duck-typed stand-in for ishares_holdings_service.ETFHolding."""

    ticker: str
    name: str
    sector: str
    weight: float
    currency: str
    asset_class: str
    location: str


def _info(ticker: str, sec: _Sec) -> dict:
    return {
        "symbol": ticker,
        "shortName": f"{ticker} Holdings",
        "quoteType": "EQUITY",
        "sector": sec.sector,
        "industry": sec.industry,
        "country": sec.country,
        "currency": sec.currency,
        "beta": sec.beta,
        "marketCap": 10_000_000_000,
    }


def _synthetic_returns(ticker: str, sec: _Sec, index: pd.DatetimeIndex, factors: pd.DataFrame,
                       idio: pd.Series) -> pd.Series:
    f = factors.reindex(index)
    systematic = (f[FACTORS] * np.array(sec.betas)).sum(axis=1, min_count=1).fillna(0.0)
    rf = f["RF"].ffill().fillna(0.0)
    return rf + systematic + sec.idio * idio.reindex(index).fillna(0.0)


def _price_frames() -> dict:
    ff = ff_decimal("daily")
    frames = {}
    for ticker, sec in UNIVERSE.items():
        close = generate_history(ticker)["Close"].loc[PRICE_START:]
        r = _synthetic_returns(ticker, sec, close.index, ff, close.pct_change())
        r.iloc[0] = 0.0
        px = (40.0 * (1.0 + r).cumprod()).round(6)
        frames[ticker] = pd.DataFrame(
            {"Open": px, "High": px, "Low": px, "Close": px, "Adj Close": px, "Volume": 1_000_000},
            index=close.index,
        )
    return frames


def _weighted(returns: pd.DataFrame, weights: dict) -> pd.Series:
    return (returns[list(weights)] * pd.Series(weights)).sum(axis=1)


@pytest.fixture
def risk_universe(isolated_state, fake_yahoo) -> SimpleNamespace:
    """The ``_QT_TEST_`` portfolio / benchmark with returns built from FakeYahoo prices."""
    for ticker, frame in _price_frames().items():
        fake_yahoo.overrides[ticker] = frame
        fake_yahoo.info_overrides[ticker] = _info(ticker, UNIVERSE[ticker])
    raw = fake_yahoo.download(list(UNIVERSE), start=PRICE_START, end="2026-07-01", auto_adjust=False)
    close = raw["Close"]
    returns_full = close.pct_change().iloc[1:]
    assert not returns_full.isna().any().any()  # every fixture ticker trades on every bar
    ticker_returns = returns_full.loc[RISK_START:]

    weights = {t: s.port for t, s in UNIVERSE.items() if s.port > 0}
    benchmark_weights = {t: s.bench for t, s in UNIVERSE.items() if s.bench > 0}
    holdings = {
        t: _Holding(t, f"{t} Holdings", UNIVERSE[t].sector, w, UNIVERSE[t].currency, "Equity",
                    HOLDING_LOCATION.get(t, "United States"))
        for t, w in benchmark_weights.items()
    }
    SectorOverrideService.set_override(*SECTOR_OVERRIDE)

    ff = ff_decimal("daily")
    rf = ff["RF"].reindex(ticker_returns.index).ffill().fillna(0.0)
    return SimpleNamespace(
        yahoo=fake_yahoo,
        close=close,
        returns_full=returns_full,
        ticker_returns=ticker_returns,
        excess=ticker_returns.sub(rf, axis=0),
        portfolio_returns=_weighted(ticker_returns, weights),
        benchmark_returns=_weighted(ticker_returns, benchmark_weights),
        weights=weights,
        benchmark_weights=benchmark_weights,
        tickers=list(weights),
        holdings=holdings,
        ff=ff,
    )


def _fits(u: SimpleNamespace) -> dict:
    """FactorModelService fits of every universe ticker (deterministic order)."""
    out = {}
    for ticker in sorted(u.excess.columns):
        sec = UNIVERSE[ticker]
        out[ticker] = FactorModelService.run_factor_regression(
            ticker, u.excess[ticker], u.ff, sector=sec.sector, country=sec.country, use_cache=False,
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot helpers
# ─────────────────────────────────────────────────────────────────────────────


def _fit_snapshot(fit) -> dict:
    """risk_analytics FactorRegressionResult minus the wall-clock regression_date."""
    return {
        "ticker": fit.ticker,
        "alpha": fit.alpha,
        "betas": fit.betas,
        "r_squared": fit.r_squared,
        "adj_r_squared": fit.adj_r_squared,
        "t_stats": fit.t_stats,
        "p_values": fit.p_values,
        "n_observations": fit.n_observations,
        "sector": fit.sector,
        "country": fit.country,
        "idio_vol": fit.idio_vol,
        "factor_vol": fit.factor_vol,
        "residuals": frame_digest(fit.residuals),
        "fitted_values": frame_digest(fit.fitted_values),
    }


def _array_digest(values) -> dict:
    return frame_digest(pd.Series(np.asarray(values, dtype="float64"), name="value"))["data"]["value"]


def _factor_regression_snapshot(res) -> dict:
    """factor_models FactorRegressionResult (arrays reduced to digests)."""
    dates = pd.DatetimeIndex(res.dates)
    return {
        "model_key": res.model_key,
        "model_name": res.model_name,
        "factor_names": res.factor_names,
        "frequency": res.frequency,
        "n_observations": res.n_observations,
        "annualization_factor": res.annualization_factor,
        "alpha": res.alpha,
        "alpha_annualized": res.alpha_annualized,
        "betas": res.betas,
        "std_errors": res.std_errors,
        "t_stats": res.t_stats,
        "p_values": res.p_values,
        "ci_lower": res.ci_lower,
        "ci_upper": res.ci_upper,
        "r_squared": res.r_squared,
        "adj_r_squared": res.adj_r_squared,
        "f_statistic": res.f_statistic,
        "f_p_value": res.f_p_value,
        "durbin_watson": res.durbin_watson,
        "residual_std_error": res.residual_std_error,
        "confidence_level": res.confidence_level,
        "dates": {"len": len(dates), "first": dates[0], "last": dates[-1]},
        "asset_excess_returns": _array_digest(res.asset_excess_returns),
        "factor_contributions": {k: _array_digest(v) for k, v in res.factor_contributions.items()},
        "alpha_series": _array_digest(res.alpha_series),
        "residuals": _array_digest(res.residuals),
    }


def _ordered(d: dict) -> dict:
    """Golden form of a service dict whose ORDER is part of the output."""
    return {"order": list(d), "items": d}


def _textbook_adj_r2(r2: float, n: int, n_predictors: int) -> float:
    return 1.0 - (1.0 - r2) * (n - 1) / (n - n_predictors - 1)


# ═════════════════════════════════════════════════════════════════════════════
# ken_french_loader
# ═════════════════════════════════════════════════════════════════════════════


def test_ken_french_fetch_fixture_datasets_golden(factor_web):
    out = {}
    for ds in KF_DATASETS:
        full = kfl.fetch_ff_dataset(ds)
        assert full.index.name == "Date"
        assert all(dt == np.float64 for dt in full.dtypes)
        out[ds] = {
            "full": frame_digest(full),
            "start_2026": frame_digest(kfl.fetch_ff_dataset(ds, start="2026-01-01")),
        }
    assert_golden("ken_french_fetch", out, AREA)

    # One GET per call, to <base><dataset>_CSV.zip with a browser UA and a 30 s timeout.
    assert [r["url"] for r in factor_web.requests] == [kf_url(ds) for ds in KF_DATASETS for _ in (0, 1)]
    assert {r["user_agent"] for r in factor_web.requests} == {"Mozilla/5.0"}
    assert {r["timeout"] for r in factor_web.requests} == {30.0}


def test_ken_french_monthly_parse_stops_before_annual_block(factor_web):
    ff5 = kfl.fetch_ff_dataset(KF_FF5_MONTHLY)
    mom = kfl.fetch_ff_dataset(KF_MOM_MONTHLY)
    assert list(ff5.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    assert list(mom.columns) == ["Mom"]  # the ",Mom   " header cell is stripped
    for frame in (ff5, mom):
        assert len(frame) == 59  # 2021-07 .. 2026-05; the "Annual Factors" rows are dropped
        assert frame.index[0] == pd.Timestamp("2021-07-01")
        assert frame.index[-1] == pd.Timestamp("2026-05-01")  # YYYYMM -> first of month
    # identical to an independent read of the fixture table
    pd.testing.assert_frame_equal(ff5, _kf_table(KF_FF5_MONTHLY), check_names=False, check_freq=False)


def test_ken_french_parse_edge_cases(factor_web):
    text = "\r\n".join([
        "Preamble line one, with a comma inside",
        "Missing data are indicated by -99.99 or -999. \xa9 _QT_TEST_",  # latin-1 byte
        "",
        ",A ,  B  ,C",
        "202001,  1.00,  2.00,  3.00",
        "202002,  x,  2.50,  3.50",  # non-numeric -> row skipped
        "202003,  4.00",  # short row -> NaN padded
        "202004, -99.99, -999,  0.00, 7.00",  # sentinels kept as numbers; extra cell ignored
        "",
        " Annual Factors: January-December ",
        ",A,B,C",
        "  2020,  1.0,  2.0,  3.0",
        "",
    ]) + "\r\n"
    factor_web.serve_kf_text("_QT_TEST_edge", text)
    df = kfl.fetch_ff_dataset("_QT_TEST_edge")
    assert list(df.columns) == ["A", "B", "C"]
    assert list(df.index) == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-03-01"), pd.Timestamp("2020-04-01")]
    jan, mar, apr = (pd.Timestamp(d) for d in ("2020-01-01", "2020-03-01", "2020-04-01"))
    assert df.loc[jan].tolist() == [1.0, 2.0, 3.0]
    assert df.loc[mar, "A"] == 4.0
    assert df.loc[mar, ["B", "C"]].isna().all()
    assert df.loc[apr].tolist() == [-99.99, -999.0, 0.0]

    # ``start`` keeps rows ON or after the date
    started = kfl.fetch_ff_dataset("_QT_TEST_edge", start="2020-03-01")
    assert list(started.index) == [pd.Timestamp("2020-03-01"), pd.Timestamp("2020-04-01")]

    # 8-digit dates -> daily index
    factor_web.serve_kf_text("_QT_TEST_daily", ",X\n20240102, 0.5\n20240103,-0.25\n")
    daily = kfl.fetch_ff_dataset("_QT_TEST_daily")
    assert list(daily.index) == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]
    assert daily["X"].tolist() == [0.5, -0.25]

    # the first *.csv member is used whatever its case
    factor_web.serve_kf_text("_QT_TEST_member", ",X\n202401, 1.5\n", member="_qt_test_lower.csv")
    assert kfl.fetch_ff_dataset("_QT_TEST_member")["X"].tolist() == [1.5]


def test_ken_french_errors(factor_web):
    factor_web.serve_kf_text("_QT_TEST_noheader", "just text\n202001, 1.0\n")
    with pytest.raises(ValueError, match="Could not locate header row"):
        kfl.fetch_ff_dataset("_QT_TEST_noheader")

    factor_web.serve_kf_text("_QT_TEST_norows", "preamble\n\n,A,B\n\nAnnual\n")
    with pytest.raises(ValueError, match="No data rows parsed"):
        kfl.fetch_ff_dataset("_QT_TEST_norows")

    factor_web.routes[kf_url("_QT_TEST_nocsv")] = _zip_bytes("readme.txt", b"no csv here")
    with pytest.raises(ValueError, match="No CSV inside Ken French zip"):
        kfl.fetch_ff_dataset("_QT_TEST_nocsv")

    factor_web.fail.add(kf_url(KF_FF5_DAILY))
    with pytest.raises(urllib.error.URLError):
        kfl.fetch_ff_dataset(KF_FF5_DAILY)


# ═════════════════════════════════════════════════════════════════════════════
# FactorDataService (factor_models)
# ═════════════════════════════════════════════════════════════════════════════

CUSTOM_MONTHLY = FactorModelSpec(
    name="_QT_TEST_custom_monthly", key="_qt_test_custom_monthly", factors=("Mkt-RF", "R_IA", "BAB"),
    source="custom", description="_QT_TEST_", min_frequency="monthly",
)
CUSTOM_DAILY = FactorModelSpec(
    name="_QT_TEST_custom_daily", key="_qt_test_custom_daily", factors=("Mkt-RF", "SMB", "R_ROE"),
    source="custom", description="_QT_TEST_", min_frequency="daily",
)


def test_factor_data_get_factors_golden(factor_env):
    web = factor_env.web
    out = {}
    specs = [MODELS[k] for k in ("capm", "ff3", "carhart4", "ff5", "ff5mom", "q4", "q5",
                                 "aqr_bab", "aqr_qmj", "aqr_full")] + [CUSTOM_MONTHLY, CUSTOM_DAILY]
    for freq in ("daily", "weekly", "monthly"):
        for spec in specs:
            try:
                factors, rf = FactorDataService.get_factors(spec, freq)
            except ValueError as exc:
                out[f"{spec.key}.{freq}"] = {"error": str(exc)}
                continue
            assert list(factors.columns) == list(spec.factors)
            out[f"{spec.key}.{freq}"] = {"factors": frame_digest(factors), "rf": frame_digest(rf)}
    assert_golden("factor_data_get_factors", out, AREA)

    # AQR data is monthly-only: daily/weekly AQR models fail validation.
    assert out["aqr_bab.daily"] == {"error": "Factor data missing columns ['BAB'] for model FF3 + BAB. "
                                             "The data source may be unavailable."}
    assert "error" in out["aqr_full.weekly"] and "error" in out["_qt_test_custom_monthly.daily"]
    for loaded in ("aqr_full.monthly", "_qt_test_custom_monthly.monthly", "q5.weekly", "_qt_test_custom_daily.daily"):
        assert "factors" in out[loaded], loaded
    # Every dataset is fetched once (in this order); later frequencies/models hit the
    # memory cache.  (pandas may open an .xlsx URL more than once per read.)
    counts = Counter(web.urls())
    assert list(counts) == [
        f"{KF_FF5_DAILY}_CSV.zip", f"{KF_MOM_DAILY}_CSV.zip",
        "q5_factors_daily_2023.csv",
        f"{KF_FF5_MONTHLY}_CSV.zip", f"{KF_MOM_MONTHLY}_CSV.zip",
        "q5_factors_monthly_2023.csv",
        "Betting-Against-Beta-Equity-Factors-Monthly.xlsx",
        "Quality-Minus-Junk-Factors-Monthly.xlsx",
        "The-Devil-in-HMLs-Details-Factors-Monthly.xlsx",
    ]
    assert all(n == 1 for name, n in counts.items() if not name.endswith(".xlsx"))


def test_factor_data_ff_matches_fixture_tables(factor_env):
    """Daily/monthly FF = FF5 inner-join Mom (renamed UMD) / 100; weekly = W-FRI sums."""
    daily, rf_d = FactorDataService.get_factors(MODELS["ff5mom"], "daily")
    expected = ff_decimal("daily")
    pd.testing.assert_frame_equal(daily, expected[FACTORS], check_names=False, check_freq=False)
    pd.testing.assert_series_equal(rf_d, expected["RF"], check_names=False, check_freq=False)
    assert pd.Timestamp("2025-08-15") not in daily.index  # missing from the momentum file

    weekly, rf_w = FactorDataService.get_factors(MODELS["ff5mom"], "weekly")
    exp_w = expected.resample("W-FRI").sum()
    pd.testing.assert_frame_equal(weekly, exp_w[FACTORS], check_names=False, check_freq=False)
    pd.testing.assert_series_equal(rf_w, exp_w["RF"], check_names=False, check_freq=False)

    monthly, rf_m = FactorDataService.get_factors(MODELS["ff5mom"], "monthly")
    exp_m = ff_decimal("monthly")
    pd.testing.assert_frame_equal(monthly, exp_m[FACTORS], check_names=False, check_freq=False)
    assert monthly.index[0] == pd.Timestamp("2021-07-01")  # month-START index


def test_factor_data_cache_same_day_then_stale(factor_env):
    web, cache_dir = factor_env.web, FactorDataService._CACHE_DIR
    first, _ = FactorDataService.get_factors(MODELS["ff5mom"], "daily")
    assert len(web.requests) == 2
    assert {p.name for p in cache_dir.iterdir()} == {
        "ff_daily.parquet", "ff_daily_last_update.txt",
    }

    FactorDataService.get_factors(MODELS["ff3"], "weekly")  # weekly is derived from the daily cache
    assert len(web.requests) == 2

    FactorDataService._memory.clear()  # disk cache written today is reused
    again, _ = FactorDataService.get_factors(MODELS["ff5mom"], "daily")
    assert len(web.requests) == 2
    pd.testing.assert_frame_equal(again, first, check_freq=False)

    # A timestamp from yesterday is stale ("fresh" == updated today) -> re-download.
    stamp = cache_dir / "ff_daily_last_update.txt"
    stamp.write_text((datetime.now() - timedelta(days=1)).isoformat())
    FactorDataService.get_factors(MODELS["ff5mom"], "daily")
    assert web.urls()[2:] == [f"{KF_FF5_DAILY}_CSV.zip", f"{KF_MOM_DAILY}_CSV.zip"]
    assert datetime.fromisoformat(stamp.read_text()).date() == datetime.now().date()


def test_factor_data_requests_from_1963(factor_env, monkeypatch):
    calls = []
    real = kfl.fetch_ff_dataset

    def recording(dataset_name, start=None):
        calls.append((dataset_name, start))
        return real(dataset_name, start=start)

    monkeypatch.setattr(kfl, "fetch_ff_dataset", recording)
    FactorDataService.get_factors(MODELS["capm"], "daily")
    FactorDataService.get_factors(MODELS["capm"], "monthly")
    assert calls == [
        (KF_FF5_DAILY, "1963-01-01"), (KF_MOM_DAILY, "1963-01-01"),
        (KF_FF5_MONTHLY, "1963-01-01"), (KF_MOM_MONTHLY, "1963-01-01"),
    ]


def test_factor_data_clear_cache_wipes_the_shared_factor_dir(factor_env):
    ffs = _fama_french_service()
    FactorDataService.get_factors(MODELS["capm"], "daily")
    ffs.get_factor_returns()
    cache_dir = FactorDataService._CACHE_DIR
    assert ffs._CACHE_DIR == cache_dir
    assert {p.name for p in cache_dir.iterdir()} == {
        "ff_daily.parquet", "ff_daily_last_update.txt",
        "fama_french.parquet", "fama_french_last_update.txt",
    }
    FactorDataService.clear_cache()
    # It deletes EVERY file in the shared directory, including FamaFrenchDataService's cache.
    assert list(cache_dir.iterdir()) == []
    assert FactorDataService._memory == {}
    assert ffs.is_data_current() is False


# ═════════════════════════════════════════════════════════════════════════════
# FamaFrenchDataService (risk_analytics)
# ═════════════════════════════════════════════════════════════════════════════


def test_fama_french_outputs_golden(factor_env):
    ffs = _fama_french_service()
    out = {
        "factor_returns": frame_digest(ffs.get_factor_returns()),
        "risk_free": frame_digest(ffs.get_risk_free_rate()),
        "factor_returns_window": frame_digest(ffs.get_factor_returns("2025-09-01", "2025-12-31")),
        "risk_free_window": frame_digest(ffs.get_risk_free_rate("2025-09-01", "2025-12-31")),
        "factor_returns_from": frame_digest(ffs.get_factor_returns(start_date="2026-05-01")),
        "risk_free_until": frame_digest(ffs.get_risk_free_rate(end_date="2024-12-31")),
    }
    assert_golden("fama_french_data", out, AREA)
    assert factor_env.web.urls() == [f"{KF_FF5_DAILY}_CSV.zip", f"{KF_MOM_DAILY}_CSV.zip"]
    assert out["factor_returns"]["columns"] == FACTORS  # RF is exposed separately


def test_fama_french_and_factor_data_daily_agree(factor_env):
    """Both services build the same daily frame from the same two zips (P8 merges them)."""
    ffs = _fama_french_service()
    factors, rf = FactorDataService.get_factors(MODELS["ff5mom"], "daily")
    pd.testing.assert_frame_equal(ffs.get_factor_returns(), factors, check_freq=False)
    pd.testing.assert_series_equal(ffs.get_risk_free_rate(), rf, check_freq=False)
    # ...but they keep separate caches, so the zips are downloaded twice.
    assert factor_env.web.urls().count(f"{KF_FF5_DAILY}_CSV.zip") == 2


def test_fama_french_requests_from_1990_and_30_day_staleness(factor_env, monkeypatch):
    ffs = _fama_french_service()
    web = factor_env.web
    calls = []
    real = kfl.fetch_ff_dataset
    monkeypatch.setattr(kfl, "fetch_ff_dataset",
                        lambda name, start=None: calls.append((name, start)) or real(name, start=start))

    first = ffs.get_factor_returns()
    assert calls == [(KF_FF5_DAILY, "1990-01-01"), (KF_MOM_DAILY, "1990-01-01")]

    ffs._cached_data = None  # disk cache (< 30 days old) is reused
    pd.testing.assert_frame_equal(ffs.get_factor_returns(), first, check_freq=False)
    assert len(web.requests) == 2

    ffs._TIMESTAMP_FILE.write_text((datetime.now() - timedelta(days=29, hours=23)).isoformat())
    assert ffs.is_data_current() is True
    ffs.get_risk_free_rate()
    assert len(web.requests) == 2

    ffs._TIMESTAMP_FILE.write_text((datetime.now() - timedelta(days=30, minutes=1)).isoformat())
    assert ffs.is_data_current() is False
    ffs.get_factor_returns()
    assert len(web.requests) == 4


# ═════════════════════════════════════════════════════════════════════════════
# FactorModelService (risk_analytics) vs the OLSRegressionService kernel
# ═════════════════════════════════════════════════════════════════════════════


def _kernel_inputs(u: SimpleNamespace, ticker: str):
    """The exact X / y FactorModelService regresses for ``ticker``."""
    y = u.excess[ticker].dropna()
    dates = y.index.intersection(u.ff.index)
    X = np.column_stack([np.ones(len(dates)), u.ff.loc[dates, FactorModelService.CORE_FACTORS].values])
    return dates, X, y.loc[dates].values


def test_factor_model_regressions_golden(risk_universe):
    fits = _fits(risk_universe)
    assert all(fit is not None for fit in fits.values())
    batch = FactorModelService.run_portfolio_regressions(
        risk_universe.excess.assign(_QT_TEST_SHORT=risk_universe.excess["_QT_TEST_ALPHA"].where(
            np.arange(len(risk_universe.excess)) < 100)),
        risk_universe.ff,
        {t: {"sector": s.sector, "country": s.country} for t, s in UNIVERSE.items()},
        max_workers=4,
        use_cache=False,
    )
    # < MIN_OBSERVATIONS (126) usable rows -> silently skipped
    assert sorted(batch) == sorted(UNIVERSE)
    for ticker, fit in batch.items():
        assert _fit_snapshot(fit) == _fit_snapshot(fits[ticker])

    assert_golden("factor_model_regressions", {t: _fit_snapshot(f) for t, f in fits.items()}, AREA)
    # The planted loadings are recovered (sanity of the fixture, not a tolerance on the service).
    for ticker, fit in fits.items():
        assert fit.betas["Mkt-RF"] == pytest.approx(UNIVERSE[ticker].betas[0], abs=0.25)


def test_factor_model_min_observations(risk_universe):
    ex, ff = risk_universe.excess["_QT_TEST_ALPHA"], risk_universe.ff
    common = ex.index.intersection(ff.index)
    assert FactorModelService.run_factor_regression(
        "_QT_TEST_ALPHA", ex.loc[common[:125]], ff, use_cache=False) is None
    fit = FactorModelService.run_factor_regression("_QT_TEST_ALPHA", ex.loc[common[:126]], ff, use_cache=False)
    assert fit.n_observations == 126
    # NaN / inf returns are dropped before counting
    holed = ex.copy()
    holed.iloc[[3, 5]] = [np.nan, np.inf]
    assert FactorModelService.run_factor_regression(
        "_QT_TEST_ALPHA", holed, ff, use_cache=False).n_observations == len(common) - 2


def test_factor_model_service_matches_run_ols_kernel(risk_universe):
    """Same X / y -> same betas, t, p, R^2, residuals and fitted values as ``_run_ols``."""
    names = ["const"] + FactorModelService.CORE_FACTORS
    for ticker, fit in _fits(risk_universe).items():
        dates, X, y = _kernel_inputs(risk_universe, ticker)
        ols = OLSRegressionService._run_ols(X, y)
        assert fit.n_observations == ols["n"] == len(dates)
        np.testing.assert_allclose([fit.betas[n] for n in names], ols["betas"], rtol=1e-10, atol=1e-15)
        np.testing.assert_allclose([fit.t_stats[n] for n in names], ols["t_stats"], rtol=1e-10)
        np.testing.assert_allclose([fit.p_values[n] for n in names], ols["p_values"], rtol=1e-9, atol=1e-15)
        assert fit.r_squared == pytest.approx(ols["r_squared"], rel=1e-12)
        np.testing.assert_allclose(fit.residuals.values, ols["residuals"], rtol=1e-10, atol=1e-15)
        np.testing.assert_allclose(fit.fitted_values.values, ols["fitted"], rtol=1e-10, atol=1e-15)
        assert list(fit.residuals.index) == list(dates)
        assert fit.alpha == fit.betas["const"]
        # vols use numpy's population std (ddof=0) of residuals / fitted values
        assert fit.idio_vol == pytest.approx(np.std(ols["residuals"]) * math.sqrt(252), rel=1e-10)
        assert fit.factor_vol == pytest.approx(np.std(ols["fitted"]) * math.sqrt(252), rel=1e-10)


def test_factor_model_adj_r2_current_formula(risk_universe):
    """Documents today's value: (n-1)/(n-k-1) with k = 7 columns INCLUDING the intercept."""
    for ticker, fit in _fits(risk_universe).items():
        n, k = fit.n_observations, 1 + len(FactorModelService.CORE_FACTORS)
        current = 1 - (1 - fit.r_squared) * (n - 1) / (n - k - 1)
        assert fit.adj_r_squared == pytest.approx(min(1.0, max(0.0, current)), rel=1e-12)
        assert 0.0 < fit.adj_r_squared < _textbook_adj_r2(fit.r_squared, n, k - 1)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="KNOWN-BUG:adj-r2 FactorModelService adjusted R^2 uses (n-1)/(n-k-1) with k incl. the "
           "intercept (one degree of freedom too many); the textbook / _run_ols value is (n-1)/(n-k)",
)
def test_factor_model_adj_r2_matches_textbook_and_run_ols(risk_universe):
    for ticker, fit in _fits(risk_universe).items():
        _dates, X, y = _kernel_inputs(risk_universe, ticker)
        ols = OLSRegressionService._run_ols(X, y)
        textbook = _textbook_adj_r2(fit.r_squared, fit.n_observations, len(FactorModelService.CORE_FACTORS))
        assert ols["adj_r_squared"] == pytest.approx(textbook, rel=1e-12)
        assert fit.adj_r_squared == pytest.approx(ols["adj_r_squared"], rel=1e-12)


# ═════════════════════════════════════════════════════════════════════════════
# FactorRegressionService (factor_models) on FactorDataService data
# ═════════════════════════════════════════════════════════════════════════════


def _monthly_asset_returns(ticker: str) -> pd.Series:
    """Month-END asset returns over the monthly fixture (like ``resample('ME')`` in the module)."""
    ff_m = ff_decimal("monthly")
    ff_m.index = ff_m.index.to_period("M").to_timestamp(how="end").normalize()
    close = generate_history(ticker)["Close"].resample("ME").last()
    return _synthetic_returns(ticker, UNIVERSE[ticker], ff_m.index, ff_m, close.pct_change()).rename(ticker)


def test_factor_regression_service_golden(factor_env, risk_universe):
    ticker = "_QT_TEST_ALPHA"
    daily = risk_universe.returns_full[ticker]
    assets = {
        "daily": daily,
        "weekly": (1 + daily).resample("W-FRI").prod() - 1,
        "monthly": _monthly_asset_returns(ticker),
    }
    cases = [("capm", "daily"), ("ff5mom", "daily"), ("q4", "daily"), ("carhart4", "weekly"),
             ("ff5", "weekly"), ("ff3", "monthly"), ("q5", "monthly"), ("aqr_full", "monthly")]
    out = {}
    for key, freq in cases:
        spec = MODELS[key]
        factors, rf = FactorDataService.get_factors(spec, freq)
        res = FactorRegressionService.run_regression(assets[freq], factors, rf, spec, freq)
        # This kernel (_run_ols) already uses the textbook adjusted R^2.
        assert res.adj_r_squared == pytest.approx(
            _textbook_adj_r2(res.r_squared, res.n_observations, len(spec.factors)), rel=1e-12)
        out[f"{key}.{freq}"] = _factor_regression_snapshot(res)

    # q-factor daily data only overlaps 2025-06..2025-12, too short for a weekly fit (< 60 weeks).
    q_weekly, rf_weekly = FactorDataService.get_factors(MODELS["q4"], "weekly")
    with pytest.raises(ValueError, match=r"Insufficient observations: \d+ \(weekly\), need at least 60"):
        FactorRegressionService.run_regression(assets["weekly"], q_weekly, rf_weekly, MODELS["q4"], "weekly")
    assert_golden("factor_regression_service", out, AREA)


# ═════════════════════════════════════════════════════════════════════════════
# FactorRiskService contribution methods
# ═════════════════════════════════════════════════════════════════════════════


def test_factor_risk_contributions_golden(risk_universe):
    u = risk_universe
    fits = _fits(u)
    pw, bw = u.weights, u.benchmark_weights
    residuals = FactorRiskService.calculate_portfolio_residuals(fits, pw)
    summary = FactorRiskService.calculate_risk_summary(fits, pw, bw, u.portfolio_returns, u.benchmark_returns)
    tar = summary["total_active_risk"]
    ctev_by_group = FactorRiskService.calculate_factor_ctev_by_group(fits, pw, bw, tar)
    security_risks = FactorRiskService.calculate_all_security_risks(fits, pw, bw)
    sector_industry = FactorRiskService.calculate_sector_industry_contributions(pw, bw, tar, fits)

    from app.ui.modules.risk_analytics.services.factor_model_service import (
        FactorRegressionResult as SecurityFit,
    )

    alpha = fits["_QT_TEST_ALPHA"]
    bare = SecurityFit(ticker=alpha.ticker, betas=dict(alpha.betas), r_squared=alpha.r_squared,
                       residuals=alpha.residuals, fitted_values=alpha.fitted_values)  # idio/factor vol = 0
    even = {"_QT_TEST_ALPHA": 0.5, "_QT_TEST_BRAVO": 0.5}
    out = {
        "security_metrics": {
            t: FactorRiskService.calculate_security_risk_metrics(t, fit, pw.get(t, 0.0), bw.get(t, 0.0))
            for t, fit in fits.items()
        },
        "security_metrics_from_residuals": FactorRiskService.calculate_security_risk_metrics(
            alpha.ticker, bare, 0.40, 0.25),
        "portfolio_residuals": frame_digest(residuals),
        "idio_ctev": {
            t: FactorRiskService.calculate_idiosyncratic_ctev(
                t, fit, residuals, pw.get(t, 0.0) - bw.get(t, 0.0), residuals.var())
            for t, fit in fits.items()
        },
        "summary": summary,
        "ctev_by_group": ctev_by_group,
        "ctev_by_group_zero_te": FactorRiskService.calculate_factor_ctev_by_group(fits, pw, bw, 0.0),
        "ctev_by_group_no_active_bets": FactorRiskService.calculate_factor_ctev_by_group(fits, even, even, tar),
        "security_risks": security_risks,
        "security_risks_unfitted": FactorRiskService.calculate_all_security_risks(
            fits, pw, {**bw, "_QT_TEST_GOLF": 0.05}).get("_QT_TEST_GOLF"),
        "factor_contributions": _ordered(
            FactorRiskService.calculate_factor_contributions(fits, pw, bw, tar, ctev_by_group)),
        "factor_contributions_fallback": _ordered(
            FactorRiskService.calculate_factor_contributions(fits, pw, bw, tar)),
        "industry_contributions": _ordered(
            FactorRiskService.calculate_industry_contributions(fits, pw, bw, u.holdings)),
        "sector_industry_contributions": _ordered({
            s: {**v, "industries": _ordered(v["industries"])} for s, v in sector_industry.items()
        }),
        "sector_contributions": _ordered(FactorRiskService.calculate_sector_contributions(pw, bw, tar, fits)),
        "sector_contributions_default_r2": _ordered(
            FactorRiskService.calculate_sector_contributions(pw, bw, tar, None)),
        "currency_contributions": FactorRiskService.calculate_currency_contributions(pw, bw, u.holdings),
        "currency_contributions_metadata_only": FactorRiskService.calculate_currency_contributions(pw, bw),
        "country_contributions": FactorRiskService.calculate_country_contributions(pw, bw, u.holdings),
        "country_contributions_metadata_only": FactorRiskService.calculate_country_contributions(pw, bw),
    }
    assert_golden("factor_risk_contributions", out, AREA)

    # Plain invariants / branches worth calling out
    assert FactorRiskService.validate_risk_decomposition(security_risks, summary, ctev_by_group) == []
    assert FactorRiskService.validate_risk_decomposition({}, {"factor_risk_pct": 60.0, "idio_risk_pct": 30.0},
                                                         {}) == ["Factor (60.0%) + Idio (30.0%) != 100%"]
    assert set(out["ctev_by_group_zero_te"]) == {"Market", "Style", "Sector", "Industry", "Country"}
    assert all(v == {"ctev": 0.0, "active_weight": 0.0} for v in out["ctev_by_group_zero_te"].values())
    assert FactorRiskService.calculate_idiosyncratic_ctev(
        alpha.ticker, alpha, residuals.iloc[:9], 0.15, residuals.var()) == 0.0  # < 10 aligned rows
    assert FactorRiskService.calculate_idiosyncratic_ctev(alpha.ticker, alpha, residuals, 0.15, 0.0) == 0.0
    assert FactorRiskService.calculate_risk_summary(
        fits, pw, bw, u.portfolio_returns.iloc[:9], u.benchmark_returns.iloc[:9]) == {
        "total_active_risk": 0.0, "factor_risk_pct": 50.0, "idio_risk_pct": 50.0,
        "ex_ante_beta": 1.0, "ex_post_beta": 1.0,
    }
    # "Not Classified" is always listed last
    assert out["sector_industry_contributions"]["items"]["Technology"]["industries"]["order"][-1] == "Not Classified"


# ═════════════════════════════════════════════════════════════════════════════
# RiskAnalyticsService
# ═════════════════════════════════════════════════════════════════════════════


def _analysis_snapshot(analysis: dict) -> dict:
    snap = {"keys": sorted(analysis)}
    for key, value in analysis.items():
        if key == "regression_results":
            snap[key] = {t: _fit_snapshot(f) for t, f in value.items()}
        elif key == "sector_industry_contributions":
            snap[key] = _ordered({s: {**v, "industries": _ordered(v["industries"])} for s, v in value.items()})
        elif key in ("ctev_by_sector", "factor_contributions", "industry_contributions", "sector_contributions"):
            snap[key] = _ordered(value)
        else:
            snap[key] = value
    return snap


def test_risk_analytics_full_analysis_golden(factor_env, risk_universe):
    u = risk_universe
    analysis = RiskAnalyticsService.get_full_analysis(
        u.portfolio_returns, u.benchmark_returns, u.ticker_returns, u.tickers,
        u.weights, u.benchmark_weights, None, u.holdings,
    )
    snap = _analysis_snapshot(analysis)
    assert_golden("risk_analytics_full", snap, AREA)

    assert sorted(analysis["regression_results"]) == sorted(UNIVERSE)
    # ctev_by_sector honours the sector override; the Sector/Industry drill-downs do not (yet).
    assert SECTOR_OVERRIDE[1] in analysis["ctev_by_sector"]
    assert SECTOR_OVERRIDE[1] not in analysis["sector_contributions"]
    assert UNIVERSE[SECTOR_OVERRIDE[0]].sector in analysis["sector_contributions"]
    # Factor data came from the FF daily zips only (FamaFrenchDataService today).
    assert set(factor_env.web.urls()) == {f"{KF_FF5_DAILY}_CSV.zip", f"{KF_MOM_DAILY}_CSV.zip"}


def test_risk_analytics_fallback_and_summary_golden(factor_env, risk_universe):
    u = risk_universe
    # 1) Fama-French download fails -> heuristic fallback
    factor_env.web.fail.update(kf_url(ds) for ds in KF_DATASETS)
    no_factors = RiskAnalyticsService.get_full_analysis(
        u.portfolio_returns, u.benchmark_returns, u.ticker_returns, u.tickers,
        u.weights, u.benchmark_weights, None, u.holdings,
    )
    assert factor_env.web.urls() == [f"{KF_FF5_DAILY}_CSV.zip"]

    # 2) Factors load but every regression lacks data (< 126 rows) -> the same fallback
    factor_env.web.fail.clear()
    short = u.ticker_returns.iloc[-100:]
    no_fits = RiskAnalyticsService.get_full_analysis(
        _weighted(short, u.weights), _weighted(short, u.benchmark_weights), short, u.tickers,
        u.weights, u.benchmark_weights, None, u.holdings,
    )
    out = {
        "fallback_no_factor_data": _analysis_snapshot(no_factors),
        "fallback_no_regressions": _analysis_snapshot(no_fits),
        "summary_metrics": RiskAnalyticsService.get_summary_metrics(
            u.portfolio_returns, u.benchmark_returns, u.tickers, u.weights),
        "total_active_risk": RiskAnalyticsService.calculate_total_active_risk(
            u.portfolio_returns, u.benchmark_returns),
        "ex_post_beta": RiskAnalyticsService.calculate_ex_post_beta(u.portfolio_returns, u.benchmark_returns),
        # _QT_TEST_DELTA has no Yahoo beta -> the other 90 % of weight is renormalised
        "ex_ante_beta": RiskAnalyticsService.calculate_ex_ante_beta(u.tickers, u.weights),
        "ex_ante_beta_full_coverage": RiskAnalyticsService.calculate_ex_ante_beta(
            ["_QT_TEST_ALPHA", "_QT_TEST_BRAVO"], {"_QT_TEST_ALPHA": 0.6, "_QT_TEST_BRAVO": 0.4}),
    }
    assert_golden("risk_analytics_fallback", out, AREA)

    assert "regression_results" not in no_factors and "regression_results" not in no_fits
    assert out["ex_ante_beta"] == pytest.approx((0.4 * 1.3 + 0.3 * 1.1 + 0.2 * 0.95) / 0.9)
    assert out["ex_ante_beta_full_coverage"] == pytest.approx(0.6 * 1.3 + 0.4 * 1.1)  # >= 0.99: no renormalising
    # degenerate inputs
    assert RiskAnalyticsService.calculate_total_active_risk(u.portfolio_returns.iloc[:1],
                                                            u.benchmark_returns.iloc[:1]) == 0.0
    assert RiskAnalyticsService.calculate_ex_post_beta(u.portfolio_returns.iloc[:9],
                                                       u.benchmark_returns.iloc[:9]) == 1.0
    assert RiskAnalyticsService.calculate_ex_ante_beta(["_QT_TEST_DELTA"], {"_QT_TEST_DELTA": 1.0}) == 1.0
