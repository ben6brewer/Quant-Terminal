"""Render characterization of every registered FRED / yfinance data module (P0.T2).

One test, parametrized over every class in ``app.core.config.ALL_MODULES``
that subclasses ``FredDataModule`` (yfinance-backed ``YFinanceDataModule``
subclasses included).  For each module:

1. The module is built under ``qtbot`` with the real ``ThemeManager``
   ('bloomberg'), inside a fresh temp home, at a fixed size, shown offscreen
   with ``_data_initialized`` pre-set so ``showEvent`` does not start a fetch.
2. Its real service callable (``module.get_data_service()``) is called
   directly, with no worker thread. It runs against FakeFred / FakeYahoo.
   In-memory service caches are cleared first, and ``date.today()`` is frozen
   at the fakes' as-of date (2026-06-30) in the module code that reads it
   (FOMC calendar, ZQ contract months, the "Today" yield curve).
3. ``module._on_data_fetched(result)`` renders the result (snapshot
   ``default``, plus the toolbar's label texts).  Then the test selects,
   through the toolbar widgets, every view / data-mode value the toolbar
   exposes, for lookbacks ``5Y`` and ``Max``.  A toolbar without one of those
   uses its nearest option: the shortest for 5Y, the longest for Max.  CPI's
   headline/breakdown switch is a setting, so it is driven through
   ``_on_settings_changed``.  After each selection the event loop runs until
   the layout settles, and the visible view is snapshotted with
   ``golden_utils.snapshot_chart``.  Tables and the treemap get extra digests.
4. The ThemeManager is cycled dark -> light -> bloomberg.  pytest-qt fails the
   test if any slot raises, and the per-theme colours are snapshotted.
5. A mouse move is simulated at the centre of the last render's plot, and the
   tooltip text is recorded (``None`` if the view has no tooltip label).

Everything for one module goes into ``tests/goldens/fred_render/<id>.json``.
Refresh with ``--full --update-goldens`` ONLY in a Behavior-Change commit.

Known bug captured here: ``money_velocity`` crashes while rendering, because
``strftime("Q%q %Y")`` raises ValueError on Windows
(strict xfail, ``KNOWN-BUG:money-velocity-qfmt``).
"""

from __future__ import annotations

import datetime as _dt
import importlib
import itertools
import re

import pytest

from app.core.config import ALL_MODULES
from golden_utils import assert_golden, canonicalize, find_plot_items, simulate_hover, snapshot_chart

pytestmark = [pytest.mark.ui, pytest.mark.golden]

AREA = "fred_render"
AS_OF = _dt.date(2026, 6, 30)            # FakeFred END_DATE == FakeYahoo AS_OF
THEMES = ("dark", "light", "bloomberg")   # ThemeManager.set_theme's accepted names
LOOKBACKS = ("5Y", "Max")
MODULE_SIZE = (1400, 850)

KNOWN_BUGS = {
    "money_velocity": pytest.mark.xfail(
        strict=True,
        raises=ValueError,
        reason="KNOWN-BUG:money-velocity-qfmt: MoneyVelocityChart.update_data formats "
               "quarters with strftime('Q%q %Y'); '%q' is not a strftime directive "
               "(ValueError: Invalid format string on Windows)",
    ),
}

# Views selected via settings, not the toolbar: (setting key, values).
SETTING_VIEWS = {
    "cpi": ("show_breakdown", (True, False)),   # headline chart vs component breakdown
}

# Module-level ``date`` bindings whose ``today()`` drives what gets rendered.
_FROZEN_DATE_TARGETS = (
    "app.ui.modules.rate_probability.services.fomc_calendar_service.date",
    "app.ui.modules.rate_probability.services.rate_probability_service.date",
    "app.ui.modules.treasury.treasury_module.date",
)

# Offline stand-in for the Wikipedia constituent table (stock_heatmap).
_HEATMAP_CONSTITUENTS = (
    ("_QT_TEST_AAA", "_QT_TEST Alpha Corp", "Information Technology", "Software"),
    ("_QT_TEST_BBB", "_QT_TEST Beta Corp", "Information Technology", "Semiconductors"),
    ("_QT_TEST_CCC", "_QT_TEST Gamma Corp", "Information Technology", "Hardware"),
    ("_QT_TEST_DDD", "_QT_TEST Delta Corp", "Health Care", "Pharmaceuticals"),
    ("_QT_TEST_EEE", "_QT_TEST Epsilon Corp", "Health Care", "Biotechnology"),
    ("_QT_TEST_FFF", "_QT_TEST Zeta Corp", "Financials", "Banks"),
    ("_QT_TEST_GGG", "_QT_TEST Eta Corp", "Financials", "Insurance"),
    ("_QT_TEST_HHH", "_QT_TEST Theta Corp", "Energy", "Oil & Gas"),
)

_TIMESTAMP_RE = re.compile(r"^Updated:")


class _FrozenDate(_dt.date):
    """``datetime.date`` whose ``today()`` is the fakes' as-of date."""

    @classmethod
    def today(cls):
        return _dt.date(AS_OF.year, AS_OF.month, AS_OF.day)


# ─────────────────────────────────────────────────────────────────────────────
# Parametrization
# ─────────────────────────────────────────────────────────────────────────────


def _load_class(entry):
    module_path, class_name = entry["class"].split(":")
    return getattr(importlib.import_module(module_path), class_name)


def _fred_entries():
    from app.ui.modules.fred_base_module import FredDataModule

    return [e for e in ALL_MODULES if issubclass(_load_class(e), FredDataModule)]


def pytest_generate_tests(metafunc):
    """Parametrize over the registered FredDataModule classes.

    Finding them means importing every module class. That only happens with
    ``--full``, the only mode in which these ``ui`` tests run, so a non-UI
    run's collection stays cheap and does not fill ``sys.modules``.
    """
    if "fred_entry" not in metafunc.fixturenames:
        return
    if not metafunc.config.getoption("--full"):
        metafunc.parametrize("fred_entry", [pytest.param(None, id="needs-full")])
        return
    params = [
        pytest.param(e, id=e["id"], marks=[KNOWN_BUGS[e["id"]]] if e["id"] in KNOWN_BUGS else [])
        for e in _fred_entries()
    ]
    assert params, "no FredDataModule subclasses registered in app.core.config.ALL_MODULES"
    metafunc.parametrize("fred_entry", params)


# ─────────────────────────────────────────────────────────────────────────────
# Isolation: in-memory caches, frozen clock, non-FRED/Yahoo sources
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def offline_services(monkeypatch, fake_fred, fake_yahoo, fresh_home):
    """Empty in-memory caches, frozen ``date.today()``, faked constituents/logos."""
    import pandas as pd

    import app.services.base_fred_service as base_fred_service
    from app.services.ticker_metadata_service import TickerMetadataService
    from app.ui.modules.metals.services.metals_yfinance_service import MetalsYFinanceService
    from app.ui.modules.rate_probability.services.fomc_calendar_service import FomcCalendarService
    from app.ui.modules.rate_probability.services.rate_probability_service import RateProbabilityService
    from app.ui.modules.stock_heatmap.services.sp500_heatmap_service import SP500HeatmapService

    monkeypatch.setattr(base_fred_service, "_version_checked", False)
    monkeypatch.setattr(TickerMetadataService, "_cache", None)
    monkeypatch.setattr(MetalsYFinanceService, "_data", None)
    monkeypatch.setattr(MetalsYFinanceService, "_last_fetch", None)
    monkeypatch.setattr(FomcCalendarService, "_scraped_dates", None)
    monkeypatch.setattr(RateProbabilityService, "_futures_cache", None)
    monkeypatch.setattr(RateProbabilityService, "_target_rate_cache", None)
    monkeypatch.setattr(RateProbabilityService, "_historical_cache", {})
    monkeypatch.setattr(SP500HeatmapService, "_cache", {})
    monkeypatch.setattr(SP500HeatmapService, "_cache_times", {})

    for target in _FROZEN_DATE_TARGETS:
        monkeypatch.setattr(target, _FrozenDate)

    constituents = pd.DataFrame(
        list(_HEATMAP_CONSTITUENTS), columns=["ticker", "name", "sector", "sub_industry"]
    )
    monkeypatch.setattr(
        SP500HeatmapService, "_fetch_constituents",
        classmethod(lambda cls, market: constituents.copy()),
    )
    monkeypatch.setattr(SP500HeatmapService, "_fetch_logos", classmethod(lambda cls, tickers: {}))
    return fake_fred, fake_yahoo


# ─────────────────────────────────────────────────────────────────────────────
# Toolbar controls
# ─────────────────────────────────────────────────────────────────────────────


def _combo_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def _combo_axis(combo):
    return [(combo.itemText(i), (lambda c=combo, i=i: c.setCurrentIndex(i))) for i in range(combo.count())]


def _view_axis(toolbar):
    """(label, select) pairs for the toolbar's view selector (combo or tab buttons)."""
    from PySide6.QtWidgets import QButtonGroup, QComboBox

    combo = getattr(toolbar, "view_combo", None)
    if isinstance(combo, QComboBox):
        return _combo_axis(combo)
    for attr in ("view_group", "button_group"):
        group = getattr(toolbar, attr, None)
        if isinstance(group, QButtonGroup):
            return [(btn.text(), btn.click) for btn in group.buttons()]
    return []


def _data_axis(toolbar):
    from PySide6.QtWidgets import QComboBox

    combo = getattr(toolbar, "data_combo", None)
    return _combo_axis(combo) if isinstance(combo, QComboBox) else []


def _lookback_axis(toolbar):
    """5Y and Max, or the toolbar's shortest / longest option when it lacks them."""
    from PySide6.QtWidgets import QComboBox

    combo = getattr(toolbar, "lookback_combo", None)
    if not isinstance(combo, QComboBox):
        return []
    options = [t for t in _combo_items(combo) if t != "Custom"]
    assert options, "lookback combo has no options"
    wanted = []
    for label, fallback in zip(LOOKBACKS, (options[0], options[-1])):
        choice = label if label in options else fallback
        if choice not in wanted:
            wanted.append(choice)

    def select(text, c=combo):
        idx = c.findText(text)
        assert idx >= 0, f"lookback {text!r} not in {_combo_items(c)}"
        c.setCurrentIndex(idx)

    return [(t, (lambda t=t: select(t))) for t in wanted]


def _setting_axis(module, module_id):
    if module_id not in SETTING_VIEWS:
        return []
    key, values = SETTING_VIEWS[module_id]

    def select(value):
        module.settings_manager.update_settings({key: value})
        module._on_settings_changed({key: value})

    return [(f"{key}={v}", (lambda v=v: select(v))) for v in values]


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot helpers
# ─────────────────────────────────────────────────────────────────────────────


def _current_view(module):
    """The widget the user is looking at: the stack's current page, else ``module.chart``."""
    from PySide6.QtWidgets import QStackedWidget

    stack = getattr(module, "stack", None)
    if isinstance(stack, QStackedWidget) and stack.currentWidget() is not None:
        return stack.currentWidget()
    return module.chart


def _table_digest(table):
    rows, cols = table.rowCount(), table.columnCount()

    def text(item):
        return None if item is None else item.text()

    return {
        "shown": not table.isHidden(),
        "headers": [text(table.horizontalHeaderItem(c)) for c in range(cols)],
        "cells": [[text(table.item(r, c)) for c in range(cols)] for r in range(rows)],
    }


def _heatmap_digest(widget):
    tiles = [
        [d["ticker"], d.get("sector"), d["pct_change"], d["weight"], d.get("market_cap")]
        for d in (widget._heatmap_data or [])
    ]
    return {
        "placeholder": {"text": widget._placeholder_text, "shown": bool(widget._show_placeholder)},
        "view_mode": widget._view_mode,
        "tiles": sorted(tiles, key=lambda t: t[0]),
        "rects": [[d["ticker"], r.x(), r.y(), r.width(), r.height()] for r, d in widget._rects],
        "sector_rects": [[name, r.x(), r.y(), r.width(), r.height()] for r, name in widget._sector_rects],
    }


def _snapshot(widget):
    """snapshot_chart plus the state of non-pyqtgraph views (tables, treemap)."""
    from PySide6.QtWidgets import QTableWidget

    snap = snapshot_chart(widget)
    tables = ([widget] if isinstance(widget, QTableWidget) else []) + widget.findChildren(QTableWidget)
    if tables:
        snap["tables"] = canonicalize([_table_digest(t) for t in tables])
    if hasattr(widget, "_heatmap_data") and hasattr(widget, "_rects"):
        snap["heatmap"] = canonicalize(_heatmap_digest(widget))
    return snap


def _colours(snap):
    """Theme-dependent part of a snapshot: background, axes, and item pens/brushes."""
    keep = ("type", "name", "pen", "brush", "fill_brush", "brushes", "color", "visible")
    return {
        "background": snap.get("background"),
        "plots": [
            {"items": [{k: it[k] for k in keep if k in it} for it in p["items"]]}
            for p in snap["plots"]
        ],
        "tables": snap.get("tables"),
    }


def _toolbar_texts(toolbar):
    """Sorted visible label texts of the toolbar (stats, control captions), minus the clock."""
    from PySide6.QtWidgets import QLabel

    texts = {lbl.text() for lbl in toolbar.findChildren(QLabel)}
    return sorted(t for t in texts if t and not _TIMESTAMP_RE.match(t))


def _has_content(snap):
    """True if the snapshot shows data: a plotted item, a filled table, or treemap tiles."""
    for plot in snap["plots"]:
        for item in plot["items"]:
            if item.get("len_x") or item["type"] in ("FillBetweenItem", "BarGraphItem"):
                return True
    if any(t["cells"] for t in snap.get("tables") or []):
        return True
    return bool((snap.get("heatmap") or {}).get("tiles"))


def _layout_signature(module):
    """Geometry and view range of every ViewBox under ``module``."""
    import pyqtgraph as pg

    sig = []
    for view in module.findChildren(pg.GraphicsView):
        scene = view.scene()
        if scene is None:
            continue
        for item in scene.items():
            if isinstance(item, pg.ViewBox):
                (x0, x1), (y0, y1) = item.viewRange()
                sig.append((x0, x1, y0, y1, item.width(), item.height()))
    return sorted(sig)


def _settle(qtbot, module, max_rounds=10):
    """Wait for any worker the module started, then run the event loop until
    layout and view ranges stop changing.

    Painting can grow pyqtgraph axis text space, which re-lays out the plot
    and changes the pixel-dependent auto-range padding.  Stopping at this
    fixed point makes a snapshot independent of how many paints happened.
    """
    from PySide6.QtWidgets import QApplication

    QApplication.processEvents()
    qtbot.waitUntil(
        lambda: getattr(module, "_worker", None) is None
        and getattr(module, "_evolution_worker", None) is None,
        timeout=20_000,
    )
    previous = None
    for _ in range(max_rounds):
        QApplication.processEvents()
        current = _layout_signature(module)
        if current == previous:
            return
        previous = current
    raise AssertionError(f"layout did not settle after {max_rounds} event-loop rounds")


# ─────────────────────────────────────────────────────────────────────────────
# The test
# ─────────────────────────────────────────────────────────────────────────────


def test_fred_module_render(fred_entry, qtbot, theme_manager, offline_services):
    """Service -> _on_data_fetched -> every toolbar view x lookback -> themes -> hover."""
    module_id = fred_entry["id"]
    cls = _load_class(fred_entry)

    module = cls(theme_manager)
    qtbot.addWidget(module)
    module._data_initialized = True       # showEvent must not start a worker fetch
    module.resize(*MODULE_SIZE)
    module.show()
    qtbot.waitExposed(module)
    _settle(qtbot, module)

    # The real service, called directly on FakeFred / FakeYahoo data.
    fake_fred, fake_yahoo = offline_services
    result = module.get_data_service()()
    assert result is not None and len(result) > 0, f"{module_id}: empty service result from the fakes"
    assert fake_fred.calls or fake_yahoo.calls, f"{module_id}: result did not come from FakeFred/FakeYahoo"

    module._on_data_fetched(result)
    _settle(qtbot, module)

    golden = {
        "module": module_id,
        "size": [module.width(), module.height()],
        "toolbar_texts": _toolbar_texts(module.toolbar),
        "default": _snapshot(_current_view(module)),
    }
    assert _has_content(golden["default"]), f"{module_id}: nothing rendered from the service result"

    axes = [
        ("lookback", _lookback_axis(module.toolbar)),
        ("view", _view_axis(module.toolbar)),
        ("data", _data_axis(module.toolbar)),
        ("setting", _setting_axis(module, module_id)),
    ]
    axes = [(name, values) for name, values in axes if values]
    assert axes, f"{module_id}: toolbar exposes no lookback / view / data selector"
    golden["controls"] = {name: [label for label, _ in values] for name, values in axes}

    renders = {}
    key = "default"
    for combo in itertools.product(*[values for _, values in axes]):
        key = " ".join(f"{name}={label}" for (name, _), (label, _) in zip(axes, combo))
        for _label, select in combo:
            select()
        _settle(qtbot, module)
        renders[key] = _snapshot(_current_view(module))
        assert _has_content(renders[key]), f"{module_id} [{key}]: nothing rendered"
    golden["renders"] = renders

    # Theme cycle: every slot must survive (pytest-qt turns slot exceptions into failures).
    themes = {}
    for theme in THEMES:
        theme_manager.set_theme(theme, save_preference=False)
        _settle(qtbot, module)
        assert theme_manager.current_theme == theme
        view = _current_view(module)
        if isinstance(getattr(view, "_theme", None), str):
            assert view._theme == theme, f"{type(view).__name__} did not apply theme {theme!r}"
        themes[theme] = _colours(_snapshot(view))
    golden["themes"] = themes

    # Hover at the centre of the last render's plot. The tooltip is None when the
    # view has no tooltip label (tables, treemap, curve/spread/evolution charts).
    view = _current_view(module)
    tooltip = simulate_hover(view, 0.5, 0.5) if find_plot_items(view) else None
    golden["hover"] = {"state": key, "tooltip": tooltip}

    assert_golden(module_id, golden, area=AREA)
