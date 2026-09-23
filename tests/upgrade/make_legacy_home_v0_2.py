"""Generator for ``tests/fixtures/legacy_home_v0_2/`` (a v0.2 user's home).

HISTORICAL SCRIPT.  The fixture is what a Quant Terminal v0.2 user's
``~/.quant_terminal`` looks like.  It was generated ONCE, at P0, from the
unrefactored code (``qt-refactor/base`` + the P0.0 test harness, commit
ac1fc83).  Do NOT regenerate it after the refactor starts: once module ids,
settings keys or storage layouts change, this script would describe the new
code instead of the legacy one (it would most likely fail to import anyway).
It refuses to overwrite an existing fixture unless ``--force`` is given.

What it does (every write goes through the v0.2 code paths the UI uses):

* HOME/USERPROFILE -> a throw-away ``%TEMP%/_QT_TEST_legacy_gen_*`` directory
  BEFORE any ``app`` import; the real ``~/.quant_terminal`` and the project
  ``.env`` are never touched.  Sockets to non-localhost hosts are blocked;
  fredapi / yfinance are served by the offline fakes in ``tests/fixtures``.
* Non-default settings for EVERY registered module that has a settings
  manager (``update_settings`` like the settings dialogs / toolbars do):
  booleans flipped, lookbacks / view modes / data modes changed, plus
  deliberately conflicting values in the modules that later phases merge
  (M1 correlation+covariance, M2 rolling corr+cov, M3 housing starts+permits,
  M4 sahm_rule+recession_probability, M5 demographics+unemployment_age).
* Favorites (including every soon-to-be-merged id and one stale id),
  the theme preference, a transaction portfolio and a weights portfolio,
  a ``[Custom]`` returns import (through the Import Data parser), chart
  indicators (custom_indicators.json incl. one pre-per-line-appearance entry,
  volume_settings.json, plugin_indicator_appearance.json), a sector override,
  a saved ticker list, a custom factor model, and three FRED group parquet
  caches (+ the FRED cache version file) produced by the services under
  FakeFred.
* Copies ``<home>/.quant_terminal`` (minus price/metadata caches) into the
  fixture and writes ``expected.json``: the values the upgrade test asserts.

Usage (repo root, venv python)::

    PYTHONPATH=src python tests/upgrade/make_legacy_home_v0_2.py [--out DIR] [--force]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TESTS_DIR.parent
DEFAULT_OUT = TESTS_DIR / "fixtures" / "legacy_home_v0_2"
SIZE_BUDGET_BYTES = 200 * 1024
FIXTURE_FORMAT = 1

# ─────────────────────────────────────────────────────────────────────────────
# The user's (non-default) choices.  Values are RUNTIME values (Qt pen styles,
# colour tuples); expected.json stores their canonical JSON form.
# ─────────────────────────────────────────────────────────────────────────────

PORTFOLIO_NAME = "_QT_TEST_portfolio"
WEIGHTS_PORTFOLIO_NAME = "_QT_TEST_weights"
CUSTOM_SERIES_NAME = "_QT_TEST_series"
CUSTOM_MODEL_NAME = "_QT_TEST_model"
TICKER_LIST_NAME = "_QT_TEST_list"
SECTOR_OVERRIDE_TICKER = "_QT_TEST_TKR"

FAVORITES = [
    # soon-to-be-merged ids (M1..M5) - both halves of most pairs
    "correlation_matrix", "covariance_matrix",       # M1: both halves
    "rolling_covariance",                            # M2: only the alias half
    "housing_starts", "housing_permits",             # M3
    "sahm_rule", "recession_probability",            # M4
    "demographics", "unemployment_age",              # M5
    # ordinary favorites
    "charts", "yields", "cpi", "portfolio_construction",
    # stale id: the phantom module removed in P0.0 (a real v0.2 user could have it)
    "market_concentration",
]
THEME = "light"

LOOKBACK_PREFERENCE = ("10Y", "20Y", "Max", "5Y", "2Y", "1Y")

# view_mode / data_mode choices for modules that get the generic treatment
VIEW_CHANGES = {
    "labor_claims": {"view_mode": "YoY %"},
    "jolts": {"view_mode": "YoY %", "jolts_series": ["Job Openings", "Quits"]},
    "money_supply": {"view_mode": "YoY %", "show_m1": False},
    "gdp": {"view_mode": "YoY %", "data_mode": "Nominal", "show_imports": False},
    "industrial_production": {"view_mode": "YoY %"},
    "consumer_sentiment": {"view_mode": "YoY %"},
    "retail_sales": {"view_mode": "YoY %", "data_mode": "Real"},
    "vehicle_sales": {"view_mode": "YoY %", "show_heavy_trucks": False},
    "trade_balance": {"view_mode": "YoY %"},
    "consumer_credit": {"view_mode": "YoY %"},
    "government_debt": {"view_mode": "% GDP"},
    "metals": {"view_mode": "Raw", "show_palladium": False},
    "crude_oil": {"view_mode": "YoY %", "show_brent": False},
    "natural_gas": {"view_mode": "YoY %"},
    "household_wealth": {"view_mode": "YoY %"},
    "household_debt": {"view_mode": "Debt Service"},
    "personal_income": {"view_mode": "YoY %", "data_mode": "Real"},
    "wage_growth": {"view_mode": "Raw", "show_eci": False},
    "durable_goods": {"view_mode": "YoY %"},
    "bank_lending": {"view_mode": "YoY %", "show_consumer": False},
    "currency": {"view_mode": "YoY %"},
    "home_prices": {"view_mode": "YoY %"},
    "home_sales": {"view_mode": "YoY %"},
    "commercial_real_estate": {"view_mode": "YoY %"},
    "wealth_distribution": {"view_mode": "Line", "show_bottom50": False},
    "income_inequality": {"view_mode": "YoY %"},
    "loan_survey": {"view_mode": "By Category", "show_auto_loans": False},
    "student_loans": {"view_mode": "YoY %"},
    "population": {"view_mode": "YoY %"},
    "energy_production": {"view_mode": "YoY %"},
    "labor_market_overview": {"show_u6": True},
    "volatility": {"show_move": False, "show_oil_vol": True, "threshold_1": 25},
    "financial_stress": {"show_kcfsi": False},
    "fed_balance_sheet": {"show_breakdown": True},
    "fed_funds_rate": {"show_target_band": False},
    "reserve_balances": {"show_total_assets_overlay": True},
    "pce": {"show_core_pce": False},
    "ppi": {"show_ppi_energy": False},
    "real_rates": {"show_tips_30y": False},
    "corporate_spreads": {"show_hy": False},
    "financial_conditions": {"show_nonfin_leverage": False},
    "supply_chain": {"show_wholesale_is": False},
    "regional_pmi": {"show_dallas": False},
    "productivity": {"show_real_comp": False},
    "housing_supply": {"show_existing_supply": False},
    "delinquency_rates": {"show_crosshair": False},
    "mortgage_rates": {"show_legend": False},
    "savings_rate": {"show_crosshair": False},
    "payrolls": {"show_legend": False},
    "money_velocity": {"show_hover_tooltip": False},
    "inflation_expectations": {"show_reference_line": False},
}


def explicit_changes():
    """Fully specified per-module changes (no generic rule applied)."""
    from PySide6.QtCore import Qt

    return {
        # M1 (shared analysis_settings.json, written in registry order)
        "efficient_frontier": {"num_simulations": 5000, "ef_colorscale": "Viridis", "ef_show_cml": False,
                               "ef_allow_leverage": False, "ef_show_indifference_curve": False},
        "correlation_matrix": {"tickers": ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "KO"], "corr_decimals": 2,
                               "matrix_colorscale": "Blue-White-Red", "corr_fixed_color_scale": False,
                               "lookback_days": 1095, "periodicity": "weekly"},
        "covariance_matrix": {"cov_decimals": 6, "show_matrix_overlay": False},
        # M2 (shared rolling_settings.json)
        "rolling_correlation": {"ticker1": "SPY", "ticker2": "TLT", "rolling_window": 126, "lookback_days": 1825},
        "rolling_covariance": {"show_reference_lines": False, "line_width": 3, "line_style": Qt.DashLine,
                               "line_color": (255, 128, 0)},
        # M3
        "housing_starts": {"view_mode": "YoY %", "show_multi": False, "show_gridlines": False, "lookback": "10Y"},
        "housing_permits": {"show_sf_permits": False, "show_crosshair": False, "lookback": "20Y",
                            "show_recession_bands": False},
        # M4
        "sahm_rule": {"threshold_value": 0.6, "show_threshold": False, "show_gridlines": False, "lookback": "20Y"},
        "recession_probability": {"show_crosshair": False, "show_hover_tooltip": False, "lookback": "10Y",
                                  "show_recession_bands": False},
        # M5
        "demographics": {"demo_series": ["Black", "Hispanic", "Youth (16-24)"], "show_recession_shading": False,
                         "lookback": "10Y", "show_legend": False},
        "unemployment_age": {"age_series": ["16-19", "20-24", "65+"], "lookback": "Max", "show_gridlines": False,
                             "show_hover_tooltip": False},
        # non-FRED modules
        "charts": {"candle_up_color": (0, 200, 120), "candle_down_color": (220, 40, 90), "line_width": 3,
                   "line_style": Qt.DashLine, "show_price_label": False},
        "portfolio_construction": {"highlight_editable_fields": False, "hide_free_cash_summary": True},
        "performance_metrics": {"risk_free_source": "manual", "manual_risk_free_rate": 0.042, "decimal_places": 3,
                                "show_ytd": False, "custom_period_enabled": True, "custom_period_years": 3.0},
        "risk_analytics": {"default_benchmark": "QQQ", "show_currency_factor": False, "decimal_places": 1,
                           "collapsed_sectors": ["Technology", "Energy"]},
        "distribution_metrics": {"show_gridlines": True, "exclude_cash": False, "kde_color": (255, 64, 64),
                                 "kde_line_style": Qt.DotLine, "show_cdf_view": True,
                                 "benchmark_show_portfolio_mean": True},
        "monte_carlo": {"simulation_method": "parametric", "n_simulations": 5000, "n_years": 3, "show_mean": True,
                        "band_90_color": (40, 120, 220), "portfolio_median_line_style": Qt.DashDotLine,
                        "benchmark": "SPY", "var_confidence_level": 0.99},
        "ols_regression": {"ticker_x": "SPY", "ticker_y": "QQQ", "data_mode": "log_returns", "frequency": "weekly",
                           "lookback_days": 1825, "show_equation": False},
        "factor_models": {"input_mode": "portfolio", "portfolio": PORTFOLIO_NAME,
                          "model_key": "custom_qt_test_model", "frequency": "weekly", "lookback_days": 1095,
                          "show_only_significant": True, "confidence_level": 0.99},
        "monthly_returns": {"show_ytd": False, "use_gradient": False, "decimals": 1, "colorscale": "Viridis"},
        "asset_class_returns": {"decimals": 2, "label_mode": "ticker", "show_cagr": False, "cagr_years": 10},
        "cpi": {"show_breakdown": False, "show_headline_overlay": False, "show_legend": False,
                "show_gridlines": False},
        "yields": {"rate_series": ["2Y", "10Y", "30Y"], "show_fed_funds_rate": True, "show_inversion_shading": False,
                   "line_width": 3, "line_style": Qt.DotLine, "line_color": (255, 128, 0)},
        "rate_probability": {"show_gridlines": False, "show_futures_table": False},
        "stock_heatmap": {"view_mode": "Flat", "sizing_mode": "Equal Weight", "lookback": "1M", "show_logo": False,
                          "color_scale": 5.0},
    }


# Changed in-session but excluded from persistence by the v0.2 manager.
SESSION_ONLY_CHANGES = {
    "risk_analytics": {"lookback_days": 504, "portfolio_universe_sectors": ["Technology"]},
}


def generic_changes(defaults: dict, lookbacks) -> dict:
    ch = {}
    if "lookback" in defaults and lookbacks:
        for lb in LOOKBACK_PREFERENCE:
            if lb in lookbacks and lb != defaults["lookback"]:
                ch["lookback"] = lb
                break
    if defaults.get("show_gridlines") is True:
        ch["show_gridlines"] = False
    for key in ("show_recession_bands", "show_recession_shading"):
        if key in defaults:
            ch[key] = not defaults[key]
    return ch


# ─────────────────────────────────────────────────────────────────────────────
# Environment isolation
# ─────────────────────────────────────────────────────────────────────────────


def redirect_home() -> Path:
    if any(m == "app" or m.startswith("app.") for m in sys.modules):
        raise RuntimeError("app was imported before the home redirect")
    home = Path(tempfile.mkdtemp(prefix="_QT_TEST_legacy_gen_")).resolve()
    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)
    if os.name == "nt":
        drive, tail = os.path.splitdrive(str(home))
        os.environ["HOMEDRIVE"] = drive
        os.environ["HOMEPATH"] = tail
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    for var in [k for k in os.environ if k.upper().endswith("_API_KEY")]:
        os.environ.pop(var, None)
    if Path.home().resolve() != home:
        raise RuntimeError(f"home redirect failed: {Path.home()} != {home}")
    return home


def block_network(mp) -> None:
    local = {"localhost", "127.0.0.1", "::1", "", None}
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def _host(address):
        return address[0] if isinstance(address, tuple) and address else address

    def connect(self, address):
        if getattr(socket, "AF_UNIX", None) is not None and self.family == socket.AF_UNIX:
            return real_connect(self, address)
        if _host(address) not in local:
            raise RuntimeError(f"network blocked in legacy-home generator: {address!r}")
        return real_connect(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if host not in local:
            raise RuntimeError(f"network blocked in legacy-home generator: {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    mp.setattr(socket.socket, "connect", connect)
    mp.setattr(socket, "getaddrinfo", getaddrinfo)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers shared with the test (kept dependency-free on purpose)
# ─────────────────────────────────────────────────────────────────────────────


def canonical(value):
    """Canonical JSON form of a runtime settings value (what the test compares with)."""
    from golden_utils import canonicalize  # tests/ is on sys.path (see main)

    return canonicalize(value)


def module_entries():
    from app.core.config import MODULE_SECTIONS

    return [e for entries in MODULE_SECTIONS.values() for e in entries]


def settings_manager_for(entry):
    """v0.2 wiring: registry entry -> (manager instance, kind) or (None, None)."""
    import importlib

    from app.ui.modules.base_module import BaseModule
    from app.services.base_settings_manager import GenericSettingsManager

    mod_path, cls_name = entry["class"].split(":")
    cls = getattr(importlib.import_module(mod_path), cls_name)
    if entry["id"] == "portfolio_construction":
        from app.ui.modules.portfolio_construction.services.portfolio_settings_manager import (
            PortfolioSettingsManager,
        )
        return PortfolioSettingsManager(), "PortfolioSettingsManager"
    if issubclass(cls, BaseModule) and cls.create_settings_manager is not BaseModule.create_settings_manager:
        mgr = cls.create_settings_manager(None)  # v0.2 factories never touch self
        return mgr, type(mgr).__name__
    if hasattr(cls, "SETTINGS_FILENAME") and hasattr(cls, "DEFAULT_SETTINGS"):
        return GenericSettingsManager(cls.SETTINGS_FILENAME, cls.DEFAULT_SETTINGS), "GenericSettingsManager"
    return None, None


def lookbacks_for(entry):
    import importlib

    mod_path, cls_name = entry["class"].split(":")
    cls = getattr(importlib.import_module(mod_path), cls_name)
    fn = getattr(cls, "get_lookback_map", None)
    if fn is None:
        return None
    try:
        return list(fn(None).keys())
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Generation steps
# ─────────────────────────────────────────────────────────────────────────────


def write_settings(expected: dict) -> None:
    explicit = explicit_changes()
    by_file: dict = {}
    per_module: dict = {}
    for entry in module_entries():
        mid = entry["id"]
        mgr, kind = settings_manager_for(entry)
        if mgr is None:
            continue
        if mid in explicit:
            changes = dict(explicit[mid])
        else:
            changes = generic_changes(mgr.DEFAULT_SETTINGS, lookbacks_for(entry))
            changes.update(VIEW_CHANGES.get(mid, {}))
        unknown = set(changes) - set(mgr.DEFAULT_SETTINGS)
        if unknown:
            raise RuntimeError(f"{mid}: unknown settings keys {sorted(unknown)}")
        same = [k for k, v in changes.items() if v == mgr.DEFAULT_SETTINGS[k]]
        if same or len(changes) < 2:
            raise RuntimeError(f"{mid}: changes must be >= 2 non-default values ({same=}, {changes=})")
        session = SESSION_ONLY_CHANGES.get(mid, {})
        mgr.update_settings({**changes, **session})  # what the settings dialogs do
        by_file.setdefault(mgr.settings_filename, []).append(mid)
        per_module[mid] = {"file": mgr.settings_filename, "manager": kind, "changes": changes,
                           "session_only": session}

    # Modules sharing a file see every change written to it (union, in write order).
    for mid, info in per_module.items():
        merged = {}
        for other in by_file[info["file"]]:
            merged.update(per_module[other]["changes"])
        expected["settings"][mid] = {
            "file": info["file"],
            "manager": info["manager"],
            "shared_with": [m for m in by_file[info["file"]] if m != mid],
            "values": {k: canonical(v) for k, v in sorted(merged.items())},
            "session_only_reverts_to_default": sorted(info["session_only"]),
        }


def write_favorites_and_preferences(expected: dict) -> None:
    from app.services.favorites_service import FavoritesService
    from app.services.preferences_service import PreferencesService

    FavoritesService.initialize()
    for mid in FAVORITES:
        assert FavoritesService.toggle_favorite(mid) is True
    PreferencesService.initialize()
    PreferencesService.set_theme(THEME)
    expected["favorites"] = sorted(FAVORITES)
    expected["preferences"] = {"theme": THEME}


def write_portfolios(expected: dict) -> None:
    from app.ui.modules.portfolio_construction.services.portfolio_persistence import PortfolioPersistence
    from app.ui.modules.portfolio_construction.services.portfolio_service import PortfolioService

    PortfolioPersistence.initialize()
    tx = PortfolioService.create_transaction
    txs = [
        tx("2024-01-02", "FREE CASH", "Buy", 100000, 1.0, 0.0, "_QT_TEST_ deposit", 0),
        tx("2024-01-02", "spy", "Buy", 100, 472.65, 1.0, "", 1),
        tx("2024-01-02", "AAPL", "Buy", 150, 185.64, 1.0, "", 2),
        tx("2024-03-15", "AGG", "Buy", 200, 97.10, 0.0, "", 0),
        tx("2025-06-02", "SPY", "Sell", 30, 592.71, 1.0, "trim", 0),
        tx("2025-06-02", "FREE CASH", "Sell", 5000, 1.0, 0.0, "_QT_TEST_ withdrawal", 1),
    ]
    pf = PortfolioPersistence.create_new_portfolio(PORTFOLIO_NAME)
    pf["transactions"] = txs
    assert PortfolioPersistence.save_portfolio(pf)

    weights = {"SPY": 0.5, "AGG": 0.3, f"[Custom] {CUSTOM_SERIES_NAME}": 0.2}
    wp = PortfolioPersistence.create_new_portfolio(WEIGHTS_PORTFOLIO_NAME, "weights")
    wp["weights"] = dict(weights)
    assert PortfolioPersistence.save_portfolio(wp)

    # visit order: weights first, then the transaction portfolio (most recent)
    PortfolioPersistence.record_visit(WEIGHTS_PORTFOLIO_NAME)
    time.sleep(0.05)
    PortfolioPersistence.record_visit(PORTFOLIO_NAME)

    holdings = PortfolioService.calculate_aggregate_holdings(txs, {})
    expected["portfolios"] = {
        PORTFOLIO_NAME: {
            "type": "transaction",
            "transaction_count": len(txs),
            "transactions": [
                {k: t[k] for k in ("date", "ticker", "transaction_type", "quantity", "entry_price", "fees",
                                   "sequence", "notes")}
                for t in txs
            ],
            "tickers": ["SPY", "AAPL", "AGG"],
            "quantities": {h["ticker"]: h["total_quantity"] for h in holdings},
            "avg_cost_basis": {h["ticker"]: h["avg_cost_basis"] for h in holdings},
        },
        WEIGHTS_PORTFOLIO_NAME: {"type": "weights", "weights": weights},
    }
    expected["recent_portfolios"] = [PORTFOLIO_NAME, WEIGHTS_PORTFOLIO_NAME]


def write_custom_import(expected: dict, scratch: Path) -> None:
    import numpy as np
    import pandas as pd

    from app.services.custom_data_service import format_custom_ticker
    from app.ui.modules.import_data.import_data_module import _parse_and_save

    dates = pd.date_range("2016-01-31", "2026-05-31", freq="ME")
    rng = np.random.default_rng(20260630)
    values = np.round(rng.normal(0.006, 0.03, len(dates)), 6)
    csv = scratch / f"{CUSTOM_SERIES_NAME}.csv"
    pd.DataFrame({"Date": dates.strftime("%Y-%m-%d"), "Value": values}).to_csv(csv, index=False)
    meta = _parse_and_save(str(csv), CUSTOM_SERIES_NAME, "monthly", "Alternatives")
    expected["custom_imports"] = {
        CUSTOM_SERIES_NAME: {
            "ticker": format_custom_ticker(CUSTOM_SERIES_NAME),
            "asset_class": meta.asset_class,
            "frequency": meta.frequency,
            "start_date": meta.start_date,
            "end_date": meta.end_date,
            "row_count": meta.row_count,
            "source_filename": meta.source_filename,
            "returns_sum": float(np.sum(values)),
            "returns_first": float(values[0]),
            "returns_last": float(values[-1]),
        }
    }


def write_indicators(expected: dict) -> None:
    from PySide6.QtCore import Qt

    from app.ui.modules.chart.services.indicator_service import IndicatorService

    IndicatorService.initialize()

    def per_line(kind, tweaks):
        pla = IndicatorService._migrate_to_per_line_appearance({"kind": kind})
        for col, t in tweaks.items():
            pla[col].update(t)
        return pla

    overlays = {
        "SMA(50)": {"kind": "sma", "length": 50,
                    "per_line_appearance": per_line("sma", {"SMA": {"color": (255, 215, 0), "line_width": 3}})},
        "BB(20,2.0)": {"kind": "bbands", "length": 20, "std": 2.0,
                       "per_line_appearance": per_line("bbands", {"BB_Middle": {"visible": False}})},
        # legacy entry saved before per-line appearance existed (migrated on load)
        "EMA(21)": {"kind": "ema", "length": 21},
    }
    oscillators = {
        "RSI(14)": {"kind": "rsi", "length": 14,
                    "per_line_appearance": per_line("rsi", {"RSI": {"line_style": Qt.DashLine}})},
        "MACD(12,26,9)": {"kind": "macd", "fast": 12, "slow": 26, "signal": 9,
                          "per_line_appearance": per_line("macd", {})},
    }
    for name, cfg in overlays.items():
        IndicatorService.add_custom_indicator(name, cfg, is_overlay=True)
    for name, cfg in oscillators.items():
        IndicatorService.add_custom_indicator(name, cfg, is_overlay=False)

    volume = {"display_type": "line", "up_color": (0, 180, 90), "line_color": (200, 200, 50), "line_width": 3}
    IndicatorService.ALL_INDICATORS["Volume"].update(volume)
    IndicatorService.save_volume_settings()

    plugin = "Death/Golden Cross"
    cols = IndicatorService.preview_indicator_columns(plugin)
    if not cols:
        raise RuntimeError(f"could not preview plugin columns for {plugin!r}")
    first = cols[0]
    plugin_appearance = {
        first: {"label": first, "visible": True, "color": (255, 0, 255), "line_width": 4,
                "line_style": Qt.DotLine, "marker_shape": "o", "marker_size": 10},
    }
    IndicatorService.set_plugin_appearance(plugin, plugin_appearance)

    expected["indicators"] = {
        "overlays": {k: canonical(v) for k, v in overlays.items()},
        "oscillators": {k: canonical(v) for k, v in oscillators.items()},
        "migrated_without_per_line_appearance": ["EMA(21)"],
        "volume": canonical(volume),
        "plugin_appearance": {plugin: canonical(plugin_appearance)},
        "plugin_columns": {plugin: list(cols)},
    }


def write_fred_caches(expected: dict) -> None:
    from app.services import base_fred_service
    from app.ui.modules.housing.services.housing_fred_service import HousingFredService
    from app.ui.modules.recession.services.recession_fred_service import RecessionFredService
    from app.ui.modules.unemployment_age.services.unemployment_age_service import UnemploymentAgeService

    services = {
        "HousingFredService": (HousingFredService, "housing_monthly.parquet"),
        "RecessionFredService": (RecessionFredService, "recession_monthly.parquet"),
        "UnemploymentAgeService": (UnemploymentAgeService, "unemployment_age_monthly.parquet"),
    }
    expected["fred"] = {"version": base_fred_service._FRED_CACHE_VERSION, "services": {}}
    for name, (svc, cache_file) in services.items():
        result = svc.fetch_all_data()
        if not result:
            raise RuntimeError(f"{name}.fetch_all_data() returned nothing")
        path = base_fred_service.CACHE_DIR / cache_file
        if not path.exists():
            raise RuntimeError(f"{name} did not write {path}")
        import pandas as pd

        raw = pd.read_parquet(path)
        expected["fred"]["services"][name] = {
            "cache_file": cache_file,
            "columns": sorted(str(c) for c in raw.columns),
            "rows": int(len(raw)),
            "first_date": raw.index.min().strftime("%Y-%m-%d"),
            "last_date": raw.index.max().strftime("%Y-%m-%d"),
            "output_keys": sorted(result),
        }


def write_misc(expected: dict) -> None:
    from app.services.ticker_list_persistence import TickerListPersistence
    from app.ui.modules.factor_models.services.custom_model_store import CustomModelStore
    from app.ui.modules.risk_analytics.services.sector_override_service import SectorOverrideService

    SectorOverrideService.set_override(SECTOR_OVERRIDE_TICKER, "Technology", "Software - Infrastructure")
    tickers = ["AAPL", "MSFT", "SPY", "TLT"]
    assert TickerListPersistence.save_list(TICKER_LIST_NAME, tickers)
    spec = CustomModelStore.save_model(CUSTOM_MODEL_NAME, ["SMB", "HML", "UMD"])
    expected["sector_overrides"] = {SECTOR_OVERRIDE_TICKER.upper(): {"sector": "Technology",
                                                                     "industry": "Software - Infrastructure"}}
    expected["ticker_lists"] = {TICKER_LIST_NAME: tickers}
    expected["custom_factor_models"] = {spec.key: {"name": spec.name, "factors": list(spec.factors)}}


# ─────────────────────────────────────────────────────────────────────────────
# Copy + manifest
# ─────────────────────────────────────────────────────────────────────────────

# Everything under cache/ is regenerable; keep only the FRED group caches and
# the two cache-version markers (price-cache and FRED-cache formats of v0.2).
KEEP_CACHE = {"cache/.data_source_version", "cache/fred/.fred_cache_version",
              "cache/fred/housing_monthly.parquet", "cache/fred/recession_monthly.parquet",
              "cache/fred/unemployment_age_monthly.parquet"}

# Keep the legacy files byte-exact (v0.2 on Windows writes CRLF JSON).
GITATTRIBUTES = "# Byte-exact legacy files: no end-of-line normalisation.\n* -text\n"


def copy_tree(home: Path, out: Path) -> list:
    src = home / ".quant_terminal"
    dst = out / ".quant_terminal"
    files = []
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src).as_posix()
        if rel.startswith("cache/") and rel not in KEEP_CACHE:
            continue
        if rel.startswith("screenshots/"):
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        files.append({"path": rel, "size": p.stat().st_size})
    missing = KEEP_CACHE - {f["path"] for f in files}
    if missing:
        raise RuntimeError(f"expected cache files missing: {sorted(missing)}")
    return files


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--force", action="store_true", help="overwrite an existing fixture")
    args = ap.parse_args(argv)
    out: Path = args.out.resolve()
    if (out / ".quant_terminal").exists() and not args.force:
        print(f"refusing to overwrite {out} (historical fixture; use --force)", file=sys.stderr)
        return 2

    home = redirect_home()
    scratch = Path(tempfile.mkdtemp(prefix="_QT_TEST_legacy_src_")).resolve()
    sys.path.insert(0, str(TESTS_DIR))

    import pytest

    mp = pytest.MonkeyPatch()
    try:
        block_network(mp)
        import app.core.paths as paths_mod
        import app.services.fred_api_key_service as fks
        from fixtures.fake_fred import patch_fred
        from fixtures.fake_yahoo import patch_yahoo

        env_file = scratch / ".env"
        mp.setattr(paths_mod, "env_file_path", lambda: env_file)
        mp.setattr(fks, "env_file_path", lambda: env_file)
        mp.setattr(fks.FredApiKeyService, "_api_key", "test_api_key")
        patch_fred(mp)
        patch_yahoo(mp)

        from app.core.config import APP_VERSION

        expected = {
            "format": FIXTURE_FORMAT,
            "app_version": APP_VERSION,
            "generated_from": git_head(),
            "generator": "tests/upgrade/make_legacy_home_v0_2.py",
            "settings": {},
        }
        write_settings(expected)
        write_favorites_and_preferences(expected)
        write_portfolios(expected)
        write_custom_import(expected, scratch)
        write_indicators(expected)
        write_fred_caches(expected)
        write_misc(expected)

        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        files = copy_tree(home, out)
        total = sum(f["size"] for f in files)
        if total > SIZE_BUDGET_BYTES:
            raise RuntimeError(f"fixture too large: {total} bytes > {SIZE_BUDGET_BYTES}")
        expected["files"] = files
        expected["total_bytes"] = total
        (out / "expected.json").write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8", newline="\n")
        (out / ".gitattributes").write_text(GITATTRIBUTES, encoding="utf-8", newline="\n")
        print(f"wrote {len(files)} files ({total} bytes) to {out}")
    finally:
        mp.undo()
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(scratch, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
