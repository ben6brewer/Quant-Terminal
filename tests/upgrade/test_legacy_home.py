"""Upgrade path: a v0.2 user home (``tests/fixtures/legacy_home_v0_2``) loads.

The fixture was generated ONCE from the unrefactored code by
``tests/upgrade/make_legacy_home_v0_2.py``; ``expected.json`` next to it lists
the user's (non-default) choices.  The ``legacy_home`` fixture copies the tree
into a fresh temporary home; the tests load it with the CURRENT code:

* every registered module's settings manager returns the saved values
  (Qt pen styles / colour tuples deserialised, session-only keys dropped,
  untouched keys at their defaults, the file not rewritten by loading);
* favorites (incl. the ids later merged: covariance_matrix, rolling_covariance,
  housing_permits, sahm_rule, recession_probability, demographics,
  unemployment_age), the theme preference, both portfolios, the ``[Custom]``
  import, chart indicators (custom / volume / plugin appearance JSONs), the
  sector override, the saved ticker list and the custom factor model;
* the FRED group parquet caches are served as-is (no fetch) and can be
  refreshed incrementally without losing history.

HOW TO EXTEND (later phases): the fixture is frozen - never regenerate it.
When module ids, settings keys or storage layouts change, keep these tests
green by migrating the legacy data in the product code and updating only the
lookup helpers below (``settings_manager_for`` / ``LEGACY_ID_ALIASES`` /
``LEGACY_KEY_ALIASES``) plus explicit expectations for the new behaviour.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from golden_utils import canonicalize, frame_digest

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "legacy_home_v0_2"
EXPECTED = json.loads((FIXTURE_DIR / "expected.json").read_text(encoding="utf-8"))
SETTINGS_IDS = sorted(EXPECTED["settings"])

PORTFOLIO = "_QT_TEST_portfolio"
WEIGHTS_PORTFOLIO = "_QT_TEST_weights"
CUSTOM_SERIES = "_QT_TEST_series"
PLUGIN = "Death/Golden Cross"
MERGED_LATER = ["covariance_matrix", "rolling_covariance", "housing_permits", "sahm_rule",
                "recession_probability", "demographics", "unemployment_age"]

# Legacy module id -> current module id (none yet; filled when modules merge).
LEGACY_ID_ALIASES: dict = {}
# (legacy module id, legacy key) -> current key (none yet).
LEGACY_KEY_ALIASES: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# Current-code lookups (the only place to adapt when the wiring changes)
# ─────────────────────────────────────────────────────────────────────────────


def registry_entries() -> dict:
    from app.core.config import MODULE_SECTIONS

    return {e["id"]: e for entries in MODULE_SECTIONS.values() for e in entries}


def settings_manager_for(module_id: str):
    """Registry id -> the settings manager the module uses today (or None)."""
    from app.services.base_settings_manager import GenericSettingsManager
    from app.ui.modules.base_module import BaseModule

    module_id = LEGACY_ID_ALIASES.get(module_id, module_id)
    entry = registry_entries()[module_id]
    mod_path, cls_name = entry["class"].split(":")
    cls = getattr(importlib.import_module(mod_path), cls_name)
    if module_id == "portfolio_construction":  # not a BaseModule; owns its manager
        from app.ui.modules.portfolio_construction.services.portfolio_settings_manager import (
            PortfolioSettingsManager,
        )
        return PortfolioSettingsManager()
    if issubclass(cls, BaseModule) and cls.create_settings_manager is not BaseModule.create_settings_manager:
        return cls.create_settings_manager(None)  # the factories do not use self
    if hasattr(cls, "SETTINGS_FILENAME") and hasattr(cls, "DEFAULT_SETTINGS"):
        return GenericSettingsManager(cls.SETTINGS_FILENAME, cls.DEFAULT_SETTINGS)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Fixture sanity
# ─────────────────────────────────────────────────────────────────────────────


def test_fixture_inventory_matches_manifest_and_stays_small():
    tree = FIXTURE_DIR / ".quant_terminal"
    on_disk = {p.relative_to(tree).as_posix(): p.stat().st_size for p in tree.rglob("*") if p.is_file()}
    listed = {f["path"]: f["size"] for f in EXPECTED["files"]}
    assert on_disk == listed
    assert sum(on_disk.values()) == EXPECTED["total_bytes"] <= 200 * 1024
    assert EXPECTED["app_version"] == "0.2.0"

    # user-named entities use the _QT_TEST_ prefix (never real names)
    for folder in ("portfolios", "custom_data/series", "ticker_lists"):
        stems = [Path(p).stem for p in on_disk if p.startswith(folder + "/")]
        assert stems, folder
        assert all(s.startswith("_QT_TEST_") for s in stems), (folder, stems)
    assert all(t.startswith("_QT_TEST_") for t in EXPECTED["sector_overrides"])
    assert all(m["name"].startswith("_QT_TEST_") for m in EXPECTED["custom_factor_models"].values())


def test_every_module_with_settings_has_legacy_values(legacy_home, legacy_expected):
    current = {mid for mid in registry_entries() if settings_manager_for(mid) is not None}
    legacy = {LEGACY_ID_ALIASES.get(mid, mid) for mid in legacy_expected["settings"]}
    assert current == legacy
    assert len(legacy_expected["settings"]) >= 70


# ─────────────────────────────────────────────────────────────────────────────
# Module settings
# ─────────────────────────────────────────────────────────────────────────────


def _settings_problems(module_id: str, exp: dict, home: Path) -> list:
    """Every way the module's loaded settings differ from the v0.2 user's file."""
    problems = []
    legacy_file = home / exp["file"]
    before = legacy_file.read_bytes()

    mgr = settings_manager_for(module_id)
    if mgr is None:
        return [f"{module_id}: no settings manager"]
    if mgr.settings_filename != exp["file"]:
        problems.append(f"{module_id}: settings file {mgr.settings_filename!r} != legacy {exp['file']!r}")
    if len(exp["values"]) < 2:
        problems.append(f"{module_id}: fixture should hold >= 2 non-default values")

    for legacy_key, want in exp["values"].items():
        key = LEGACY_KEY_ALIASES.get((module_id, legacy_key), legacy_key)
        got = mgr.get_setting(key)
        if canonicalize(got) != want:
            problems.append(f"{module_id}.{key}: loaded {got!r}, legacy value {want!r}")
        elif not mgr.has_custom_setting(key):
            problems.append(f"{module_id}.{key}: legacy value equals the default (fixture broken?)")
        if key.endswith("_color") and want is not None and not isinstance(got, tuple):
            problems.append(f"{module_id}.{key}: not deserialised to a tuple: {got!r}")

    for key in exp["session_only_reverts_to_default"]:
        if mgr.get_setting(key) != mgr.DEFAULT_SETTINGS[key]:
            problems.append(f"{module_id}.{key}: session-only key loaded as {mgr.get_setting(key)!r}")

    for key in sorted(set(mgr.DEFAULT_SETTINGS) - set(exp["values"])):
        if canonicalize(mgr.get_setting(key)) != canonicalize(mgr.DEFAULT_SETTINGS[key]):
            problems.append(f"{module_id}.{key}: untouched by the v0.2 user but loads as {mgr.get_setting(key)!r}")

    if legacy_file.read_bytes() != before:
        problems.append(f"{module_id}: loading rewrote {exp['file']}")
    return problems


def test_module_settings_survive(legacy_home, legacy_expected):
    """All >= 70 modules at once (one legacy-home copy; per-module details in the message)."""
    problems = []
    for module_id in SETTINGS_IDS:
        problems += _settings_problems(module_id, legacy_expected["settings"][module_id], legacy_home)
    assert not problems, f"{len(problems)} legacy settings problem(s):\n  " + "\n  ".join(problems)


def test_qt_typed_settings_deserialise(legacy_home):
    """Pen styles come back as Qt enums and colours as tuples (not JSON strings/lists)."""
    from PySide6.QtCore import Qt

    chart = settings_manager_for("charts")
    assert chart.get_line_settings()["style"] == Qt.DashLine
    assert chart.get_candle_colors() == ((0, 200, 120), (220, 40, 90))

    rolling = settings_manager_for("rolling_covariance")
    assert rolling.get_setting("line_style") == Qt.DashLine
    assert rolling.get_setting("line_color") == (255, 128, 0)

    mc = settings_manager_for("monte_carlo")
    assert mc.get_setting("portfolio_median_line_style") == Qt.DashDotLine
    assert mc.get_setting("benchmark_median_line_style") == Qt.SolidLine  # untouched

    dist = settings_manager_for("distribution_metrics")
    assert dist.get_setting("kde_line_style") == Qt.DotLine
    assert dist.get_setting("normal_line_style") == Qt.DashLine  # untouched non-solid default

    treasury = settings_manager_for("yields")
    assert treasury.get_setting("line_style") == Qt.DotLine
    assert treasury.get_setting("rate_series") == ["2Y", "10Y", "30Y"]


def test_shared_and_merge_candidate_settings_files(legacy_home):
    """Modules that share a file see each other's changes; merge pairs keep distinct files."""
    corr = settings_manager_for("correlation_matrix")
    cov = settings_manager_for("covariance_matrix")
    ef = settings_manager_for("efficient_frontier")
    assert corr.get_all_settings() == cov.get_all_settings() == ef.get_all_settings()
    assert corr.get_tickers() == ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "KO"]
    assert (cov.get_cov_decimals(), corr.get_corr_decimals()) == (6, 2)
    assert corr.get_matrix_colorscale() == "Blue-White-Red"

    rc = settings_manager_for("rolling_correlation")
    rv = settings_manager_for("rolling_covariance")
    assert rc.get_all_settings() == rv.get_all_settings()
    assert (rc.get_ticker1(), rc.get_ticker2(), rc.get_rolling_window()) == ("SPY", "TLT", 126)

    # M3 / M4 / M5 pairs: separate files with deliberately different choices
    pairs = {
        ("housing_starts", "housing_permits"): ("lookback", "10Y", "20Y"),
        ("sahm_rule", "recession_probability"): ("lookback", "20Y", "10Y"),
        ("demographics", "unemployment_age"): ("lookback", "10Y", "Max"),
    }
    for (a, b), (key, va, vb) in pairs.items():
        ma, mb = settings_manager_for(a), settings_manager_for(b)
        assert ma.settings_filename != mb.settings_filename
        assert (ma.get_setting(key), mb.get_setting(key)) == (va, vb), (a, b)
    assert settings_manager_for("sahm_rule").get_setting("threshold_value") == 0.6
    assert settings_manager_for("housing_permits").get_setting("show_sf_permits") is False
    assert settings_manager_for("demographics").get_setting("demo_series") == ["Black", "Hispanic", "Youth (16-24)"]
    assert settings_manager_for("unemployment_age").get_setting("age_series") == ["16-19", "20-24", "65+"]
    # the recession-shading key still has two spellings in v0.2 (aliased in P5)
    assert settings_manager_for("demographics").get_setting("show_recession_shading") is False
    assert settings_manager_for("recession_probability").get_setting("show_recession_bands") is False


def test_risk_analytics_session_only_keys_were_not_persisted(legacy_home):
    raw = json.loads((legacy_home / "risk_analytics_settings.json").read_text(encoding="utf-8"))
    assert "lookback_days" not in raw and "portfolio_universe_sectors" not in raw
    mgr = settings_manager_for("risk_analytics")
    assert mgr.get_setting("lookback_days") == 252
    assert mgr.get_setting("portfolio_universe_sectors") is None
    assert mgr.get_setting("default_benchmark") == "QQQ"


# ─────────────────────────────────────────────────────────────────────────────
# Favorites, preferences
# ─────────────────────────────────────────────────────────────────────────────


def test_favorites_survive_including_merge_candidates(legacy_home, legacy_expected):
    from app.services.favorites_service import FavoritesService

    FavoritesService.initialize()
    assert sorted(FavoritesService.get_favorites()) == legacy_expected["favorites"]
    for mid in MERGED_LATER:
        assert FavoritesService.is_favorite(mid), mid
    # v0.2 keeps ids that are no longer registered (the removed phantom module)
    assert FavoritesService.is_favorite("market_concentration")
    assert "market_concentration" not in registry_entries()


def test_theme_preference_survives(legacy_home, legacy_expected):
    from app.services.preferences_service import PreferencesService

    PreferencesService.initialize()
    assert PreferencesService.get_theme() == legacy_expected["preferences"]["theme"] == "light"


# ─────────────────────────────────────────────────────────────────────────────
# Portfolios and the custom import
# ─────────────────────────────────────────────────────────────────────────────


def test_portfolios_survive(legacy_home, legacy_expected):
    from app.services.portfolio_data_service import PortfolioDataService
    from app.ui.modules.portfolio_construction.services.portfolio_persistence import PortfolioPersistence

    exp = legacy_expected["portfolios"]
    tx_file = legacy_home / "portfolios" / f"{PORTFOLIO}.json"
    before = tx_file.read_bytes()

    assert sorted(PortfolioPersistence.list_portfolios()) == sorted(exp)
    assert PortfolioPersistence.list_portfolios_by_recent() == legacy_expected["recent_portfolios"]

    raw = PortfolioPersistence.load_portfolio(PORTFOLIO)
    assert raw["name"] == PORTFOLIO
    loaded = [{k: t[k] for k in exp[PORTFOLIO]["transactions"][0]} for t in raw["transactions"]]
    assert loaded == exp[PORTFOLIO]["transactions"]
    assert all(t["id"] for t in raw["transactions"])
    assert tx_file.read_bytes() == before, "no sequence migration expected: v0.2 already stores sequence"

    assert PortfolioDataService.get_tickers(PORTFOLIO) == exp[PORTFOLIO]["tickers"]
    assert not PortfolioDataService.is_weights_portfolio(PORTFOLIO)
    holdings = {h.ticker: h for h in PortfolioDataService.get_holdings(PORTFOLIO)}
    assert {t: h.quantity for t, h in holdings.items()} == exp[PORTFOLIO]["quantities"]
    for ticker, cost in exp[PORTFOLIO]["avg_cost_basis"].items():
        assert holdings[ticker].avg_cost_basis == pytest.approx(cost, rel=1e-12)

    assert PortfolioDataService.is_weights_portfolio(WEIGHTS_PORTFOLIO)
    weights = PortfolioDataService.get_weights(WEIGHTS_PORTFOLIO)
    assert weights == exp[WEIGHTS_PORTFOLIO]["weights"]
    assert PortfolioDataService.get_tickers(WEIGHTS_PORTFOLIO) == list(weights)  # file order
    assert f"[Custom] {CUSTOM_SERIES}" in weights


def test_custom_import_survives(legacy_home, legacy_expected):
    from app.services import custom_data_service as cds

    exp = legacy_expected["custom_imports"][CUSTOM_SERIES]
    metas = cds.list_custom_tickers()
    assert [m.name for m in metas] == [CUSTOM_SERIES]
    meta = metas[0]
    for field in ("asset_class", "frequency", "start_date", "end_date", "row_count", "source_filename"):
        assert getattr(meta, field) == exp[field], field

    assert cds.parse_custom_ticker(exp["ticker"].upper()) == CUSTOM_SERIES  # case-insensitive
    returns = cds.get_custom_returns(CUSTOM_SERIES, interval="monthly")
    assert returns.name == exp["ticker"]
    assert len(returns) == exp["row_count"]
    assert returns.index[0].strftime("%Y-%m-%d") == exp["start_date"]
    assert returns.index[-1].strftime("%Y-%m-%d") == exp["end_date"]
    assert float(returns.sum()) == pytest.approx(exp["returns_sum"], abs=1e-12)
    assert (float(returns.iloc[0]), float(returns.iloc[-1])) == (exp["returns_first"], exp["returns_last"])
    with pytest.raises(ValueError, match="cannot serve daily"):
        cds.get_custom_returns(CUSTOM_SERIES, interval="daily")
    assert cds.custom_end_dates([exp["ticker"], "SPY"]) == {exp["ticker"]: exp["end_date"]}
    assert cds.coarsest_custom_frequency(["SPY", exp["ticker"]]) == "monthly"


def test_derived_user_data_golden(legacy_home, upgrade_golden):
    from app.services import custom_data_service as cds
    from app.services.portfolio_data_service import PortfolioDataService

    prices = {"SPY": 600.0, "AAPL": 210.0, "AGG": 99.5}
    holdings = PortfolioDataService.get_holdings(PORTFOLIO, current_prices=prices)
    upgrade_golden("derived_user_data", {
        "custom_returns_monthly": frame_digest(cds.get_custom_returns(CUSTOM_SERIES, "monthly")),
        "custom_returns_yearly": frame_digest(cds.get_custom_returns(CUSTOM_SERIES, "yearly")),
        "custom_prices_weekly_rejected": _raises(lambda: cds.get_custom_prices(CUSTOM_SERIES, "weekly")),
        "holdings": holdings,
    })


def _raises(fn) -> str:
    try:
        fn()
    except ValueError as exc:
        return f"ValueError: {exc}"
    return "no error"


# ─────────────────────────────────────────────────────────────────────────────
# Chart indicators (custom_indicators.json, volume_settings.json, plugin appearance)
# ─────────────────────────────────────────────────────────────────────────────


def test_chart_indicators_survive(legacy_home, legacy_expected, fake_yahoo):
    from PySide6.QtCore import Qt

    from app.ui.modules.chart.services.indicator_service import IndicatorService

    exp = legacy_expected["indicators"]
    IndicatorService.initialize()

    assert IndicatorService.get_overlay_names() == sorted([*exp["overlays"], PLUGIN])
    assert IndicatorService.get_oscillator_names() == sorted([*exp["oscillators"], "Volume"])
    for name in exp["overlays"]:
        assert IndicatorService.is_overlay(name)
    for name in exp["oscillators"]:
        assert not IndicatorService.is_overlay(name)

    migrated = set(exp["migrated_without_per_line_appearance"])
    for group in ("overlays", "oscillators"):
        for name, want in exp[group].items():
            got = canonicalize(IndicatorService.ALL_INDICATORS[name])
            if name in migrated:
                got.pop("per_line_appearance")
            assert got == want, name

    # the pre-per-line-appearance EMA entry is migrated from the column metadata
    ema = IndicatorService.ALL_INDICATORS["EMA(21)"]["per_line_appearance"]
    assert list(ema) == ["EMA"]
    assert tuple(ema["EMA"]["color"]) == (255, 150, 0) and ema["EMA"]["line_style"] == Qt.SolidLine
    assert IndicatorService.ALL_INDICATORS["RSI(14)"]["per_line_appearance"]["RSI"]["line_style"] == Qt.DashLine

    volume = IndicatorService.ALL_INDICATORS["Volume"]
    assert volume["builtin"] is True and volume["kind"] == "volume"
    assert volume["display_type"] == "line"
    assert volume["up_color"] == (0, 180, 90)
    assert volume["down_color"] == (200, 50, 50)
    assert volume["line_color"] == (200, 200, 50)
    assert volume["line_width"] == 3

    assert IndicatorService.CUSTOM_INDICATOR_CLASSES[PLUGIN].NAME == PLUGIN
    assert canonicalize(IndicatorService.get_plugin_appearance(PLUGIN)) == exp["plugin_appearance"][PLUGIN]
    assert IndicatorService.preview_indicator_columns(PLUGIN) == exp["plugin_columns"][PLUGIN]


# ─────────────────────────────────────────────────────────────────────────────
# FRED group caches
# ─────────────────────────────────────────────────────────────────────────────


def _fred_services():
    from app.ui.modules.housing.services.housing_fred_service import HousingFredService
    from app.ui.modules.recession.services.recession_fred_service import RecessionFredService
    from app.ui.modules.unemployment_age.services.unemployment_age_service import UnemploymentAgeService

    return {
        "HousingFredService": HousingFredService,
        "RecessionFredService": RecessionFredService,
        "UnemploymentAgeService": UnemploymentAgeService,
    }


def _force_cache_freshness(monkeypatch, fresh: bool) -> None:
    from app.services.base_fred_service import BaseFredService

    monkeypatch.setattr(BaseFredService, "_is_cache_fresh",
                        staticmethod(lambda last_date, max_age_days: fresh))


def test_fred_group_caches_served_without_fetching(legacy_home, legacy_expected, fake_fred, monkeypatch,
                                                   upgrade_golden):
    exp = legacy_expected["fred"]
    fred_dir = legacy_home / "cache" / "fred"
    before = {p.name: p.read_bytes() for p in fred_dir.iterdir()}
    assert (fred_dir / ".fred_cache_version").read_text().strip() == exp["version"]
    _force_cache_freshness(monkeypatch, True)

    outputs = {}
    for name, svc in _fred_services().items():
        result = svc.fetch_all_data()
        assert result, name
        assert sorted(result) == exp["services"][name]["output_keys"], name
        last = max(df.index.max() for df in result.values())
        assert last.strftime("%Y-%m-%d") == exp["services"][name]["last_date"], name
        assert all(not df.empty for df in result.values()), name
        outputs[name] = {key: frame_digest(df) for key, df in sorted(result.items())}

    assert fake_fred.calls == [], "a fresh legacy cache must be served without any FRED request"
    assert {p.name: p.read_bytes() for p in fred_dir.iterdir()} == before, "legacy cache must not be wiped"
    upgrade_golden("fred_outputs_from_legacy_cache", outputs)


@pytest.mark.parametrize("service_name", sorted(EXPECTED["fred"]["services"]))
def test_fred_group_cache_refreshes_incrementally(service_name, legacy_home, legacy_expected, fake_fred,
                                                   monkeypatch):
    import pandas as pd

    exp = legacy_expected["fred"]["services"][service_name]
    cache_file = legacy_home / "cache" / "fred" / exp["cache_file"]
    legacy = pd.read_parquet(cache_file)
    _force_cache_freshness(monkeypatch, False)  # the stored data is older than the TTL

    result = _fred_services()[service_name].fetch_all_data()

    assert sorted(result) == exp["output_keys"]
    assert fake_fred.calls, "a stale legacy cache must trigger an incremental update"
    assert {start for _sid, start, _end in fake_fred.calls} == {exp["last_date"]}
    refreshed = pd.read_parquet(cache_file)
    cols = list(refreshed.columns)
    assert len(fake_fred.calls) == len(cols)
    assert set(cols) <= set(exp["columns"])
    assert len(refreshed) == exp["rows"]
    # the fakes serve the same history, so the merge must reproduce the legacy rows exactly
    pd.testing.assert_frame_equal(refreshed, legacy[cols], check_freq=False)


# ─────────────────────────────────────────────────────────────────────────────
# Other user data
# ─────────────────────────────────────────────────────────────────────────────


def test_sector_override_ticker_list_and_custom_model_survive(legacy_home, legacy_expected):
    from app.services.ticker_list_persistence import TickerListPersistence
    from app.ui.modules.factor_models.services.custom_model_store import CustomModelStore
    from app.ui.modules.risk_analytics.services.sector_override_service import SectorOverrideService

    for ticker, override in legacy_expected["sector_overrides"].items():
        assert SectorOverrideService.get_override(ticker.lower()) == override
        assert SectorOverrideService.get_effective_sector(ticker) == override["sector"]
        assert SectorOverrideService.get_effective_industry(ticker) == override["industry"]
    assert SectorOverrideService.list_overrides() == legacy_expected["sector_overrides"]

    assert TickerListPersistence.list_all() == sorted(legacy_expected["ticker_lists"])
    for name, tickers in legacy_expected["ticker_lists"].items():
        assert TickerListPersistence.load_list(name) == tickers

    models = {m.key: m for m in CustomModelStore.list_models()}
    assert set(models) == set(legacy_expected["custom_factor_models"])
    for key, want in legacy_expected["custom_factor_models"].items():
        assert models[key].name == want["name"]
        assert list(models[key].factors) == want["factors"]
    # factor_models settings point at this custom model and at the legacy portfolio
    fm = settings_manager_for("factor_models")
    assert fm.get_setting("model_key") in models
    assert fm.get_setting("portfolio") == PORTFOLIO
