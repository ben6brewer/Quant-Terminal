"""Characterization: ``FredDataModule.slice_data`` (and its overrides) on
mixed-frequency frames and ISO custom dates.  [P0.T3]

Today ``slice_data`` is ROW based (``df.tail(get_lookback_map()[label])``),
except for three overrides:

* ``LaborClaimsModule``   - months * 4.33 weekly rows,
* ``FedFundsRateModule``  - ``index.max() - DateOffset(months=...)`` (ignores ISO dates),
* ``StockHeatmapModule``  - own map, ``YTD`` from the wall clock (frozen here).

A "profile" is ``<slice implementation>.<lookback map>``; every registered FRED
module maps onto one profile (``TreasuryModule`` uses the base slice with its own
copy of the days map, ``MetalsModule`` the yfinance days map, ...).

Widget-free part: each profile is evaluated UNBOUND on a light proxy (no
QWidget) over deterministic FakeFred / FakeYahoo frames for every lookback
label any toolbar can emit plus ISO dates; the row count and first/last dates
are goldened in ``tests/goldens/settings/slice_data.profile.<profile>.json``.

Widget part (``@pytest.mark.ui``): every registered Macro module is built
offscreen; its toolbar lookback options, initial lookback and profile are
goldened in ``slice_data.module.<id>.json`` and every offered label is driven
through the real ``toolbar.lookback_changed`` signal and checked against the
profile.  Restart tests check that the chosen lookback is saved.

The widget-free tests run in the default (non ``--full``) suite; only the
``@pytest.mark.ui`` tests need ``--full``.

P2 (B-slice) makes the slice date based: regenerate the ``slice_data.profile.*``
goldens in that Behavior-Change commit, drop the KNOWN-BUG:fred-rowcount-lookback
marker, and revisit ``test_row_based_5y_on_native_frequencies`` (P5 again when
the per-module maps die).
"""

from __future__ import annotations

import datetime as _dt
import importlib
import inspect
from functools import lru_cache

import pandas as pd
import pytest

from app.core.config import MODULE_SECTIONS
from fixtures.fake_fred import END_DATE, generate_series
from fixtures.fake_yahoo import generate_history
from golden_utils import assert_golden

AREA = "settings"

# The lookback maps that exist today, spelled out literally so the test does
# not depend on the LOOKBACK_* constants that later phases delete.
KNOWN_MAPS = {
    "months": {"1Y": 12, "2Y": 24, "5Y": 60, "10Y": 120, "20Y": 240, "Max": None},
    "weeks": {"1Y": 52, "2Y": 104, "5Y": 260, "10Y": 520, "20Y": 1040, "Max": None},
    "quarters": {"5Y": 20, "10Y": 40, "20Y": 80, "Max": None},
    "days": {"1Y": 252, "2Y": 504, "5Y": 1260, "10Y": 2520, "20Y": 5040, "Max": None},
    "years": {"10Y": 10, "20Y": 20, "30Y": 30, "Max": None},
    "heatmap": {"1D": 2, "1W": 5, "1M": 21, "3M": 63, "6M": 126, "YTD": None, "1Y": 252},
}

# slice_data implementations (the class that defines ``slice_data``)
SLICE_IMPLS = {
    "base": "app.ui.modules.fred_base_module:FredDataModule",
    "labor_claims": "app.ui.modules.labor_claims.labor_claims_module:LaborClaimsModule",
    "fed_funds_rate": "app.ui.modules.fed_funds_rate.fed_funds_rate_module:FedFundsRateModule",
    "stock_heatmap": "app.ui.modules.stock_heatmap.stock_heatmap_module:StockHeatmapModule",
}

PROFILES = [
    "base.months",
    "base.weeks",
    "base.quarters",
    "base.days",
    "base.years",
    "labor_claims.months",
    "fed_funds_rate.months",
    "stock_heatmap.heatmap",
]

# Every label any toolbar offers today (FredToolbar defaults, heatmap, income
# inequality 30Y, ...), plus ISO custom dates and "no lookback set".
STANDARD_LABELS = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "2Y", "5Y", "10Y", "20Y", "30Y", "Max"]
ISO_DATES = [
    "1960-01-01",  # before every frame starts -> whole frame
    "2020-01-15",  # mid-month weekday
    "2024-02-29",  # leap day
    "2025-06-14",  # a Saturday (not on any daily index)
    "2026-06-30",  # the fakes' last observation
    "2030-01-01",  # after the data -> empty
]
LABELS = STANDARD_LABELS + ISO_DATES + [None]

HEATMAP_CLOCK = _dt.datetime(2026, 6, 30, 12, 0)  # "now" for YTD (= fake data end)
HEATMAP_LATE_CLOCK = _dt.datetime(2027, 1, 15, 12, 0)  # a new year with no data yet
LATE_YTD = "YTD@2027-01-15"

MACRO_IDS = [e["id"] for e in MODULE_SECTIONS["Macro"]]
NO_LOOKBACK_COMBO = {"rate_probability"}  # checked in test_module_lookback_snapshot
# Modules whose lookback combo offers a "Custom" start date (checked in the test).
CUSTOM_DATE_IDS = ["cpi", "jolts", "labor_claims", "payrolls", "stock_heatmap"]

# Lookback choices that are lost on restart because the module's settings
# defaults have no "lookback" key (BaseSettingsManager.load_settings drops it).
_LOOKBACK_NOT_PERSISTED = {
    "yields": pytest.mark.xfail(strict=True, reason="KNOWN-BUG:treasury-lookback-persist"),
    "cpi": pytest.mark.xfail(strict=True, reason="KNOWN-BUG:cpi-lookback-persist"),
}


def _with_known_bugs(ids):
    return [pytest.param(i, marks=_LOOKBACK_NOT_PERSISTED[i]) if i in _LOOKBACK_NOT_PERSISTED else i
            for i in ids]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _load(spec: str):
    mod_name, cls_name = spec.split(":")
    return getattr(importlib.import_module(mod_name), cls_name)


def _module_class(module_id: str):
    for entries in MODULE_SECTIONS.values():
        for entry in entries:
            if entry["id"] == module_id:
                return _load(entry["class"])
    raise KeyError(module_id)


class _Proxy:
    """Stands in for a module instance without building a QWidget.

    Instance attributes win; anything else is looked up on ``cls`` and plain
    functions are bound to the proxy, so ``cls.slice_data(proxy, df)`` runs the
    real method body (including ``self.get_lookback_map()`` calls).
    """

    def __init__(self, cls, **attrs):
        self.__dict__["_cls"] = cls
        self.__dict__.update(attrs)

    def __getattr__(self, name):
        cls = self.__dict__["_cls"]
        raw = inspect.getattr_static(cls, name)
        if isinstance(raw, staticmethod):
            return raw.__func__
        if isinstance(raw, classmethod):
            return raw.__func__.__get__(cls)
        if inspect.isfunction(raw):
            return raw.__get__(self)
        return getattr(cls, name)


def _slice(impl_cls, lookback_map: dict, lookback, df):
    proxy = _Proxy(impl_cls, _current_lookback=lookback, get_lookback_map=lambda: dict(lookback_map))
    return impl_cls.slice_data(proxy, df)


def _slice_owner(cls) -> str:
    for klass in cls.__mro__:
        if "slice_data" in vars(klass):
            return f"{klass.__module__}:{klass.__name__}"
    raise AssertionError(f"{cls.__name__} has no slice_data")


def _profile_of(cls, lookback_map: dict) -> str:
    owner = _slice_owner(cls)
    impl = next((k for k, spec in SLICE_IMPLS.items() if spec == owner), f"custom:{owner}")
    map_name = next((k for k, m in KNOWN_MAPS.items() if m == dict(lookback_map)), "custom")
    return f"{impl}.{map_name}"


def _freeze_heatmap_clock(monkeypatch, when: _dt.datetime) -> None:
    """``StockHeatmapModule.slice_data`` reads ``datetime.now()`` for YTD."""
    mod = importlib.import_module(SLICE_IMPLS["stock_heatmap"].split(":")[0])

    class _FrozenDatetime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return when if tz is None else when.replace(tzinfo=tz)

    monkeypatch.setattr(mod, "datetime", _FrozenDatetime)


def _span(df) -> str:
    """'<rows> <first>..<last>' (compact golden form)."""
    if df is None:
        return "None"
    if len(df) == 0:
        return "0 -"
    return f"{len(df)} {df.index[0]:%Y-%m-%d}..{df.index[-1]:%Y-%m-%d}"


def _union(parts: dict, keep=None) -> pd.DataFrame:
    """Mimic ``BaseFredService._get_group``: outer-join, ffill, drop all-NaN rows."""
    df = pd.DataFrame(parts)
    df.index.name = "Date"
    df = df.ffill().dropna(how="all")
    if keep is not None:
        df = df[keep].dropna(how="all")
    return df


@lru_cache(maxsize=1)
def _frames() -> dict:
    """Deterministic frames at real FRED/Yahoo frequencies (all end <= 2026-06-30)."""
    g = generate_series
    prices = pd.DataFrame({t: generate_history(t)["Close"] for t in ("AAPL", "MSFT", "SPY")})
    prices.index.name = "Date"
    return {
        # single native frequencies (raw FRED output: holidays are NaN rows)
        "daily": g("DGS10").to_frame("DGS10"),
        "calendar_daily": g("DFEDTARU").to_frame("Upper Target"),
        "weekly_sat": g("ICSA").to_frame("Initial Claims"),
        "weekly_fri": g("NFCI").to_frame("NFCI"),
        "monthly": g("UNRATE").to_frame("Unemployment Rate"),
        "quarterly": g("GDP").to_frame("GDP"),
        "annual": g("MEHOINUSA672N").to_frame("Median HH Income"),
        "prices_daily": prices,
        # mixed-frequency union indexes, built like the FRED services build them
        "union_daily_monthly": _union({"10Y": g("DGS10"), "Unemployment": g("UNRATE")}),
        "union_effr": _union(
            {"Fed Funds Rate": g("FEDFUNDS"), "Lower Target": g("DFEDTARL"), "Upper Target": g("DFEDTARU")}
        ),
        "union_fci_nfci": _union(
            {"NFCI": g("NFCI"), "Baa-10Y Spread": g("BAA10Y"), "USREC": g("USREC")}, keep=["NFCI"]
        ),
        "union_velocity": _union(
            {"M1": g("M1SL"), "M2": g("M2SL"), "M2 Velocity": g("M2V"), "USREC": g("USREC")},
            keep=["M2 Velocity"],
        ),
    }


def _labels_for(impl_name: str) -> list:
    labels = list(LABELS)
    if impl_name == "stock_heatmap":
        labels.insert(labels.index("YTD") + 1, LATE_YTD)
    return labels


def _key(label) -> str:
    return "<None>" if label is None else str(label)


def _assert_suffix(df, res, where: str) -> None:
    """Every implementation returns a (possibly empty) tail of the input."""
    assert isinstance(res, pd.DataFrame), f"{where}: {type(res).__name__}"
    assert list(res.columns) == list(df.columns), where
    assert len(res) <= len(df), where
    if len(res):
        assert res.index.equals(df.index[len(df) - len(res):]), f"{where}: not a suffix of the input"


# ─────────────────────────────────────────────────────────────────────────────
# Widget-free: frames and profiles
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.golden
def test_slice_input_frames_golden():
    frames = _frames()
    snap = {}
    for name, df in frames.items():
        assert df.index.is_monotonic_increasing and df.index.is_unique, name
        assert df.index.max() <= END_DATE, name
        freq = pd.infer_freq(df.index) if len(df) >= 3 else None
        snap[name] = {"span": _span(df), "columns": list(df.columns), "inferred_freq": freq}
    # the unions really are mixed-frequency (denser than their slowest member)
    assert len(frames["union_daily_monthly"]) > len(frames["monthly"])
    assert len(frames["union_fci_nfci"]) > len(frames["weekly_fri"])
    assert len(frames["union_velocity"]) > 3 * len(frames["quarterly"].loc["1980":])
    assert_golden("slice_data.frames", snap, area=AREA)


@pytest.mark.golden
@pytest.mark.parametrize("profile", PROFILES)
def test_slice_profile_golden(profile, monkeypatch):
    impl_name, map_name = profile.split(".")
    impl = _load(SLICE_IMPLS[impl_name])
    lookback_map = KNOWN_MAPS[map_name]
    _freeze_heatmap_clock(monkeypatch, HEATMAP_CLOCK)

    results = {}
    for fname, df in _frames().items():
        row = {}
        for label in _labels_for(impl_name):
            if label == LATE_YTD:
                _freeze_heatmap_clock(monkeypatch, HEATMAP_LATE_CLOCK)
                res = _slice(impl, lookback_map, "YTD", df)
                _freeze_heatmap_clock(monkeypatch, HEATMAP_CLOCK)
            else:
                res = _slice(impl, lookback_map, label, df)
            _assert_suffix(df, res, f"{profile}/{fname}/{label}")
            row[_key(label)] = _span(res)
        # "Max" (and an unset lookback) never cut anything, in every implementation
        assert row["Max"] == _span(df), f"{profile}/{fname}"
        assert row["<None>"] == _span(df), f"{profile}/{fname}"
        results[fname] = row

    assert_golden(
        f"slice_data.profile.{profile}",
        {"implementation": SLICE_IMPLS[impl_name], "lookback_map": lookback_map, "results": results},
        area=AREA,
    )


@pytest.mark.parametrize("profile", PROFILES)
def test_slice_none_and_empty_passthrough(profile):
    """None and empty frames are returned untouched (same object)."""
    impl_name, map_name = profile.split(".")
    impl = _load(SLICE_IMPLS[impl_name])
    empty = pd.DataFrame({"x": pd.Series(dtype="float64")}, index=pd.DatetimeIndex([], name="Date"))
    for label in ("1Y", "Max", "2020-01-15"):
        assert _slice(impl, KNOWN_MAPS[map_name], label, None) is None
        assert _slice(impl, KNOWN_MAPS[map_name], label, empty) is empty


def test_row_based_5y_on_native_frequencies():
    """On a frame at the map's own frequency the row count ~ the label."""
    impl = _load(SLICE_IMPLS["base"])
    frames = _frames()
    for fname, map_name in (("monthly", "months"), ("weekly_fri", "weeks"),
                            ("quarterly", "quarters"), ("daily", "days")):
        res = _slice(impl, KNOWN_MAPS[map_name], "5Y", frames[fname])
        years = (res.index[-1] - res.index[0]).days / 365.25
        assert len(res) == KNOWN_MAPS[map_name]["5Y"], fname
        assert 4.7 < years < 5.0, (fname, years)


@pytest.mark.xfail(strict=True, reason="KNOWN-BUG:fred-rowcount-lookback")
@pytest.mark.parametrize(
    "fname, map_name",
    [
        ("union_fci_nfci", "weeks"),  # Financial Conditions: "5Y" shows about 1 year
        ("union_velocity", "quarters"),  # Money Velocity: quarterly data on a monthly union
        ("union_daily_monthly", "months"),
        ("union_effr", "months"),
    ],
)
def test_5y_lookback_covers_five_years_on_mixed_frames(fname, map_name):
    """A "5Y" lookback should span five calendar years whatever the row density
    of the (ffilled, mixed-frequency) frame.  Row-count slicing does not."""
    impl = _load(SLICE_IMPLS["base"])
    res = _slice(impl, KNOWN_MAPS[map_name], "5Y", _frames()[fname])
    years = (res.index[-1] - res.index[0]).days / 365.25
    assert 4.9 <= years <= 5.1, years


# ─────────────────────────────────────────────────────────────────────────────
# UI: real modules (toolbar labels, signal path, restart)
# ─────────────────────────────────────────────────────────────────────────────


def _no_worker(self, fn, *args, **kwargs):
    """Stand-in for ``BaseModule._run_worker`` (no threads, no fetches)."""
    return None


@pytest.fixture
def make_module(qapp, theme_manager, fresh_home, monkeypatch):
    """Build registry modules offscreen in an isolated home, without workers."""
    from PySide6.QtCore import QCoreApplication, QEvent

    from app.ui.modules.base_module import BaseModule

    monkeypatch.setattr(BaseModule, "_run_worker", _no_worker)
    _freeze_heatmap_clock(monkeypatch, HEATMAP_CLOCK)
    created = []

    def make(module_id: str):
        widget = _module_class(module_id)(theme_manager)
        created.append(widget)
        return widget

    yield make
    for widget in created:
        widget.hide()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _combo_items(toolbar):
    combo = getattr(toolbar, "lookback_combo", None)
    if combo is None:
        return None, None
    return [combo.itemText(i) for i in range(combo.count())], combo.currentText()


@pytest.mark.ui
@pytest.mark.golden
@pytest.mark.parametrize("module_id", MACRO_IDS)
def test_module_lookback_snapshot(module_id, make_module):
    from app.ui.modules.fred_base_module import FredDataModule

    module = make_module(module_id)
    assert isinstance(module, FredDataModule)
    lookback_map = dict(module.get_lookback_map())
    profile = _profile_of(type(module), lookback_map)
    assert not profile.startswith("custom") and not profile.endswith(".custom"), (
        f"{module_id}: unknown slice profile {profile!r}; add it to KNOWN_MAPS/SLICE_IMPLS/PROFILES"
    )

    toolbar = module.toolbar
    options, initial_text = _combo_items(toolbar)
    fred_custom_date = getattr(toolbar, "supports_custom_date", None)
    assert (options is None) == (module_id in NO_LOOKBACK_COMBO), module_id
    assert (module_id in CUSTOM_DATE_IDS) == bool(fred_custom_date and fred_custom_date()), module_id
    snap = {
        "profile": profile,
        "lookback_map": lookback_map,
        "toolbar_options": options,
        "toolbar_initial": initial_text,
        "custom_date": bool(fred_custom_date()) if fred_custom_date else None,
        "has_lookback_signal": hasattr(toolbar, "lookback_changed"),
        "initial_lookback": module._current_lookback,
        "default_setting_lookback": module.settings_manager.DEFAULT_SETTINGS.get("lookback"),
        # labels a user can pick that the map does not know (they show the whole frame)
        "offered_not_in_map": sorted(o for o in (options or []) if o != "Custom" and o not in lookback_map),
    }

    # Drive every offered label through the real signal path; the instance must
    # slice exactly like its (unbound) profile and remember the choice.
    # (rate_probability has no lookback combo at all - asserted above.)
    if module_id not in NO_LOOKBACK_COMBO:
        assert snap["has_lookback_signal"], module_id
        impl_name, map_name = profile.split(".")
        impl = _load(SLICE_IMPLS[impl_name])
        frames = _frames()
        for label in [o for o in options if o != "Custom"] + ["2020-01-15"]:
            toolbar.lookback_changed.emit(label)
            assert module._current_lookback == label, (module_id, label)
            assert module.settings_manager.get_setting("lookback") == label, (module_id, label)
            for fname in ("union_daily_monthly", "weekly_fri", "quarterly", "prices_daily"):
                got = module.slice_data(frames[fname])
                exp = _slice(impl, KNOWN_MAPS[map_name], label, frames[fname])
                assert got.index.equals(exp.index), (module_id, label, fname)

    assert_golden(f"slice_data.module.{module_id}", snap, area=AREA)


@pytest.mark.ui
@pytest.mark.parametrize("module_id", _with_known_bugs([i for i in MACRO_IDS if i not in NO_LOOKBACK_COMBO]))
def test_lookback_survives_restart(module_id, make_module):
    """A lookback picked in the toolbar is saved and re-applied by a new instance."""
    first = make_module(module_id)
    options, initial_text = _combo_items(first.toolbar)
    label = next(o for o in reversed(options) if o not in ("Custom", initial_text))
    first.toolbar.lookback_changed.emit(label)
    assert first._current_lookback == label

    second = make_module(module_id)  # "restart": reads the saved settings file
    assert second._current_lookback == label
    assert second.toolbar.lookback_combo.currentText() == label


@pytest.mark.ui
@pytest.mark.parametrize("module_id", _with_known_bugs(CUSTOM_DATE_IDS))
def test_custom_iso_lookback_survives_restart(module_id, make_module):
    """An ISO custom lookback is saved and re-applied by a new instance."""
    first = make_module(module_id)
    options, initial_text = _combo_items(first.toolbar)
    assert options[-1] == "Custom" and first.toolbar.supports_custom_date()

    first.toolbar.lookback_changed.emit("2020-01-15")
    second = make_module(module_id)  # "restart": reads the saved settings file
    assert second._current_lookback == "2020-01-15"
    frame = _frames()["union_daily_monthly"]
    assert second.slice_data(frame).index[0] == pd.Timestamp("2020-01-15")
    # The combo cannot show the date (its "Custom" item text is only replaced
    # when the dialog is used), so it stays on the default label.
    assert second.toolbar.lookback_combo.currentText() == initial_text
