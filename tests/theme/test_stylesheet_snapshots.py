"""P0.T9: stylesheet snapshot characterization, every producer x 3 themes.

Every stylesheet producer that the theming phases (P3 palette, P8 analytics
widgets, P9 templates) will rewrite is captured here for ``bloomberg``,
``dark`` and ``light``.  Each stylesheet is normalized (see ``qss_snapshot``)
to ``[[selector, [[property, value], ...]], ...]`` and compared with a golden
under ``tests/theme/goldens/``.  Templating that keeps what users see keeps
these goldens EQUAL; regenerate them (``--update-goldens``) only in a
``Behavior-Change: yes`` commit.

* ``service.*``: ``ThemeStylesheetService`` getters (pure, not ui-marked).
  ``test_every_service_getter_is_snapshotted`` fails when a getter is added
  or removed without updating the tables below (P1 deletes the dead layout
  getters: remove their rows AND their golden files).
* ``chart_theme_service.*``: ``ChartThemeService`` (pure).
* ``widget.*``: widgets built offscreen under each theme, with every
  non-empty ``styleSheet()`` in the widget tree captured
  (``{"Class#objectName": [rules, ...]}``).  Sub-widgets that have their own
  snapshot are pruned (e.g. the home screen does not repeat the tiles).
* ``test_widget_stylesheet_follows_live_theme_switch``: a widget built under
  ``bloomberg``, shown, then switched dark -> light -> bloomberg must carry
  exactly the stylesheets of a widget freshly built under that theme.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

import pytest

from qss_snapshot import (
    GOLDEN_DIR,
    THEMES,
    assert_stylesheet_golden,
    describe,
    dumps,
    parse_qss,
    widget_stylesheets,
)

# ─────────────────────────────────────────────────────────────────────────────
# ThemeStylesheetService
# ─────────────────────────────────────────────────────────────────────────────

# (golden suffix, method, kwargs): getters that return QSS text.
SERVICE_QSS_GETTERS = [
    ("get_table_stylesheet", "get_table_stylesheet", {}),
    ("get_line_edit_stylesheet", "get_line_edit_stylesheet", {}),
    ("get_line_edit_stylesheet.highlighted_false", "get_line_edit_stylesheet", {"highlighted": False}),
    ("get_combobox_stylesheet", "get_combobox_stylesheet", {}),
    ("get_combobox_stylesheet.highlighted_false", "get_combobox_stylesheet", {"highlighted": False}),
    ("get_dialog_stylesheet", "get_dialog_stylesheet", {}),
    ("get_sidebar_stylesheet", "get_sidebar_stylesheet", {}),
    ("get_content_stylesheet", "get_content_stylesheet", {}),
    ("get_controls_stylesheet", "get_controls_stylesheet", {}),
    ("get_home_button_stylesheet", "get_home_button_stylesheet", {}),
    ("get_button_stylesheet", "get_button_stylesheet", {}),
    ("get_toolbar_stylesheet", "get_toolbar_stylesheet", {}),
]

# Getters that return palette values (dict / RGB tuple / color string).
SERVICE_VALUE_GETTERS = [
    "get_colors",
    "get_background_rgb",
    "get_accent_rgb",
    "get_text_rgb",
    "get_crosshair_rgb",
    "get_chart_background_color",
    "get_chart_line_color",
]


def _plain(value):
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    assert isinstance(value, (str, int, float)), f"unexpected palette value {value!r}"
    return value


def _distinct(snapshots: dict) -> int:
    return len({dumps(s) for s in snapshots.values()})


@pytest.mark.golden
@pytest.mark.parametrize(
    "suffix, method, kwargs", SERVICE_QSS_GETTERS, ids=[row[0] for row in SERVICE_QSS_GETTERS]
)
def test_service_stylesheet_snapshot(suffix, method, kwargs):
    from app.services.theme_stylesheet_service import ThemeStylesheetService

    getter = getattr(ThemeStylesheetService, method)
    snaps = {theme: parse_qss(getter(theme, **kwargs)) for theme in THEMES}

    for theme, rules in snaps.items():
        assert rules, f"{method}({theme!r}, {kwargs}) produced no rules"
        assert all(decls for _, decls in rules), f"{method}({theme!r}) has an empty rule"
    assert _distinct(snaps) > 1, f"{method} ignores the theme"
    assert_stylesheet_golden(
        f"service.{suffix}",
        {"producer": f"ThemeStylesheetService.{method}", "kwargs": kwargs, "themes": snaps},
    )


@pytest.mark.golden
@pytest.mark.parametrize("method", SERVICE_VALUE_GETTERS)
def test_service_palette_value_snapshot(method):
    from app.services.theme_stylesheet_service import ThemeStylesheetService

    getter = getattr(ThemeStylesheetService, method)
    values = {theme: _plain(getter(theme)) for theme in THEMES}

    assert _distinct(values) > 1, f"{method} ignores the theme"
    assert_stylesheet_golden(
        f"service.{method}", {"producer": f"ThemeStylesheetService.{method}", "themes": values}
    )


def test_every_service_getter_is_snapshotted():
    from app.services.theme_stylesheet_service import ThemeStylesheetService

    public = {
        name
        for name in dir(ThemeStylesheetService)
        if name.startswith("get_") and callable(getattr(ThemeStylesheetService, name))
    }
    covered = {row[1] for row in SERVICE_QSS_GETTERS} | set(SERVICE_VALUE_GETTERS)
    assert public == covered, (
        "ThemeStylesheetService getters changed; update SERVICE_QSS_GETTERS / "
        f"SERVICE_VALUE_GETTERS (and the goldens): new={sorted(public - covered)}, "
        f"gone={sorted(covered - public)}"
    )


def test_service_colors_back_the_table_stylesheet():
    """The table stylesheet is filled from ``get_colors`` (tokens, not literals)."""
    from app.services.theme_stylesheet_service import ThemeStylesheetService

    for theme in THEMES:
        colors = ThemeStylesheetService.get_colors(theme)
        rules = dict(
            (selector, dict(decls))
            for selector, decls in parse_qss(ThemeStylesheetService.get_table_stylesheet(theme))
        )
        assert rules["QTableWidget"]["background-color"] == colors["bg"].lower()
        assert rules["QTableWidget"]["color"] == colors["text"].lower()
        assert rules["QTableWidget::item:selected"]["background-color"] == colors["accent"].lower()
        assert rules["QHeaderView::section"]["background-color"] == colors["bg_header"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# ChartThemeService
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.golden
def test_chart_theme_service_indicator_panel_snapshot():
    from app.ui.modules.chart.services.chart_theme_service import ChartThemeService

    snaps = {theme: parse_qss(ChartThemeService.get_indicator_panel_stylesheet(theme)) for theme in THEMES}
    for theme, rules in snaps.items():
        assert rules, f"indicator panel stylesheet empty for {theme}"
    assert _distinct(snaps) == 3
    assert_stylesheet_golden(
        "chart_theme_service.get_indicator_panel_stylesheet",
        {"producer": "ChartThemeService.get_indicator_panel_stylesheet", "themes": snaps},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Widgets
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WidgetSpec:
    id: str
    producer: str  # dotted path of the class under test
    build: Callable  # (theme_manager, theme) -> QWidget
    prune: Callable[[], Tuple[type, ...]] = field(default=lambda: ())
    live: Optional[str] = None  # "manager": follows ThemeManager; "set_theme": widget.set_theme(t)
    setup: Optional[Callable] = None  # (monkeypatch) -> None, run before building
    root_styled: bool = True  # False: the root itself has no sheet, only its children


def _cls(path: str):
    module, name = path.rsplit(".", 1)
    return getattr(__import__(module, fromlist=[name]), name)


def _tiny_screenshots(monkeypatch):
    # Decoding the ~75 real tile PNGs costs ~8 s per grid; pixmaps carry no stylesheet.
    from PySide6.QtGui import QPixmap

    screenshot_manager = _cls("app.utils.screenshot_manager.ScreenshotManager")
    monkeypatch.setattr(screenshot_manager, "load_or_generate", staticmethod(lambda module_id: QPixmap(8, 8)))


def _settings_module(tm, theme):
    return _cls("app.ui.modules.settings_module.SettingsModule")(tm)


def _home_screen(tm, theme):
    return _cls("app.ui.widgets.navigation.home_screen.HomeScreen")(tm)


def _home_screen_prune():
    return (
        _cls("app.ui.widgets.navigation.section_tab_bar.SectionTabBar"),
        _cls("app.ui.widgets.navigation.module_tile_grid.ModuleTileGrid"),
    )


def _section_tab_bar(tm, theme):
    return _cls("app.ui.widgets.navigation.section_tab_bar.SectionTabBar")(tm)


def _module_tile(tm, theme):
    tile_cls = _cls("app.ui.widgets.navigation.module_tile.ModuleTile")
    return tile_cls("_qt_test_tile", "_QT_TEST_ Tile", "_QT_TEST_Section", tm)


def _module_tile_grid(tm, theme):
    return _cls("app.ui.widgets.navigation.module_tile_grid.ModuleTileGrid")(tm)


def _module_tile_grid_prune():
    return (_cls("app.ui.widgets.navigation.module_tile.ModuleTile"),)


def _hub_window(tm, theme):
    from PySide6.QtWidgets import QWidget

    hub = _cls("app.ui.hub_window.HubWindow")(tm)
    # A directly-added module gets a container with the overlay Home button.
    hub.add_module("_qt_test_module", QWidget(), has_own_home_button=False)
    return hub


def _hub_window_prune():
    return (_cls("app.ui.widgets.navigation.home_screen.HomeScreen"),)


def _risk_summary_panel(tm, theme):
    return _cls("app.ui.modules.risk_analytics.widgets.risk_summary_panel.RiskSummaryPanel")(tm)


def _risk_decomposition_panel(tm, theme):
    return _cls("app.ui.modules.risk_analytics.widgets.risk_decomposition_panel.RiskDecompositionPanel")(tm)


def _security_risk_table(tm, theme):
    return _cls("app.ui.modules.risk_analytics.widgets.security_risk_table.SecurityRiskTable")(tm)


def _date_range_dialog(tm, theme):
    return _cls("app.ui.modules.return_distribution.widgets.date_range_dialog.DateRangeDialog")(tm)


def _view_tab_bar(tm, theme):
    return _cls("app.ui.modules.portfolio_construction.widgets.view_tab_bar.ViewTabBar")(tm)


def _asset_class_returns_tab_bar(tm, theme):
    return _cls("app.ui.modules.asset_class_returns.widgets.asset_class_returns_tab_bar.AssetClassReturnsTabBar")(tm)


def _asset_class_returns_table(tm, theme):
    return _cls("app.ui.modules.asset_class_returns.widgets.asset_class_returns_table.AssetClassReturnsTable")(tm)


def _chart_settings_dialog(tm, theme):
    # Default settings: the line-color preview then uses the theme's line color.
    return _cls("app.ui.modules.chart.widgets.chart_settings_dialog.ChartSettingsDialog")(tm, {})


def _create_indicator_dialog(tm, theme):
    return _cls("app.ui.modules.chart.widgets.create_indicator_dialog.CreateIndicatorDialog")(tm)


_PLUGIN_COLUMNS = ["_QT_TEST_Line", "_QT_TEST_Cross"]  # the 2nd one gets the marker controls


def _edit_plugin_setup(monkeypatch):
    # The real preview fetches BTC-USD prices to discover the plugin's columns;
    # the stylesheet snapshot only needs a fixed column list.
    indicator_service = _cls("app.ui.modules.chart.services.indicator_service.IndicatorService")
    monkeypatch.setattr(
        indicator_service, "preview_indicator_columns", staticmethod(lambda name: list(_PLUGIN_COLUMNS))
    )


def _edit_plugin_appearance_dialog(tm, theme):
    dialog_cls = _cls("app.ui.modules.chart.widgets.edit_plugin_appearance_dialog.EditPluginAppearanceDialog")
    dialog = dialog_cls(tm, "_QT_TEST_Plugin")
    assert list(dialog.line_widgets) == _PLUGIN_COLUMNS
    return dialog


def _order_book_ladder(tm, theme):
    return _cls("app.ui.modules.chart.widgets.order_book_ladder.OrderBookLadderWidget")(theme=theme)


def _order_book_panel(tm, theme):
    return _cls("app.ui.modules.chart.widgets.depth_chart.OrderBookPanel")(tm)


def _indicator_panel(tm, theme):
    return _cls("app.ui.modules.chart.widgets.indicator_panel.IndicatorPanel")(tm)


WIDGET_SPECS = [
    WidgetSpec("settings_module", "app.ui.modules.settings_module.SettingsModule",
               _settings_module, live="manager"),
    WidgetSpec("navigation.home_screen", "app.ui.widgets.navigation.home_screen.HomeScreen",
               _home_screen, prune=_home_screen_prune, live="manager", setup=_tiny_screenshots,
               root_styled=False),
    WidgetSpec("navigation.section_tab_bar", "app.ui.widgets.navigation.section_tab_bar.SectionTabBar",
               _section_tab_bar, live="manager"),
    WidgetSpec("navigation.module_tile", "app.ui.widgets.navigation.module_tile.ModuleTile",
               _module_tile, live="manager", setup=_tiny_screenshots),
    WidgetSpec("navigation.module_tile_grid", "app.ui.widgets.navigation.module_tile_grid.ModuleTileGrid",
               _module_tile_grid, prune=_module_tile_grid_prune, live="manager", setup=_tiny_screenshots),
    WidgetSpec("hub_window", "app.ui.hub_window.HubWindow",
               _hub_window, prune=_hub_window_prune, live="manager", setup=_tiny_screenshots),
    WidgetSpec("risk_analytics.risk_summary_panel",
               "app.ui.modules.risk_analytics.widgets.risk_summary_panel.RiskSummaryPanel",
               _risk_summary_panel, live="manager"),
    WidgetSpec("risk_analytics.risk_decomposition_panel",
               "app.ui.modules.risk_analytics.widgets.risk_decomposition_panel.RiskDecompositionPanel",
               _risk_decomposition_panel, live="manager"),
    WidgetSpec("risk_analytics.security_risk_table",
               "app.ui.modules.risk_analytics.widgets.security_risk_table.SecurityRiskTable",
               _security_risk_table, live="manager"),
    WidgetSpec("return_distribution.date_range_dialog",
               "app.ui.modules.return_distribution.widgets.date_range_dialog.DateRangeDialog",
               _date_range_dialog),
    WidgetSpec("portfolio_construction.view_tab_bar",
               "app.ui.modules.portfolio_construction.widgets.view_tab_bar.ViewTabBar",
               _view_tab_bar, live="manager"),
    WidgetSpec("asset_class_returns.tab_bar",
               "app.ui.modules.asset_class_returns.widgets.asset_class_returns_tab_bar.AssetClassReturnsTabBar",
               _asset_class_returns_tab_bar, live="manager"),
    WidgetSpec("asset_class_returns.table",
               "app.ui.modules.asset_class_returns.widgets.asset_class_returns_table.AssetClassReturnsTable",
               _asset_class_returns_table, live="manager"),
    WidgetSpec("chart.chart_settings_dialog",
               "app.ui.modules.chart.widgets.chart_settings_dialog.ChartSettingsDialog",
               _chart_settings_dialog),
    WidgetSpec("chart.create_indicator_dialog",
               "app.ui.modules.chart.widgets.create_indicator_dialog.CreateIndicatorDialog",
               _create_indicator_dialog),
    WidgetSpec("chart.edit_plugin_appearance_dialog",
               "app.ui.modules.chart.widgets.edit_plugin_appearance_dialog.EditPluginAppearanceDialog",
               _edit_plugin_appearance_dialog, setup=_edit_plugin_setup),
    WidgetSpec("chart.order_book_ladder",
               "app.ui.modules.chart.widgets.order_book_ladder.OrderBookLadderWidget",
               _order_book_ladder, live="set_theme"),
    WidgetSpec("chart.order_book_panel", "app.ui.modules.chart.widgets.depth_chart.OrderBookPanel",
               _order_book_panel, live="manager"),
    WidgetSpec("chart.indicator_panel", "app.ui.modules.chart.widgets.indicator_panel.IndicatorPanel",
               _indicator_panel, live="manager"),
]

_LIVE_SPECS = [spec for spec in WIDGET_SPECS if spec.live]


def _theme_manager(theme: str):
    from app.core.theme_manager import ThemeManager

    tm = ThemeManager()  # starts as "bloomberg"
    tm.set_theme(theme, save_preference=False)
    assert tm.current_theme == theme
    return tm


def _build(spec: WidgetSpec, theme: str, qtbot):
    tm = _theme_manager(theme)
    widget = spec.build(tm, theme)
    qtbot.addWidget(widget)
    return widget, tm


def _drain(qapp, rounds: int = 3) -> None:
    for _ in range(rounds):
        qapp.processEvents()


def _snapshot_diff(expected, actual) -> str:
    return "".join(
        difflib.unified_diff(
            dumps(expected).splitlines(True), dumps(actual).splitlines(True),
            fromfile="fresh", tofile="after switch", n=2,
        )
    )[:6000]


@pytest.mark.ui
@pytest.mark.golden
@pytest.mark.parametrize("spec", WIDGET_SPECS, ids=[spec.id for spec in WIDGET_SPECS])
def test_widget_stylesheet_snapshot(spec, qapp, qtbot, monkeypatch):
    if spec.setup:
        spec.setup(monkeypatch)
    prune = spec.prune()
    snaps = {}
    for theme in THEMES:
        widget, _tm = _build(spec, theme, qtbot)
        assert type(widget).__module__ + "." + type(widget).__name__ == spec.producer
        snap = widget_stylesheets(widget, prune)
        assert snap, f"{spec.id}: no stylesheet anywhere in the widget tree under {theme}"
        root = describe(widget)
        assert (root in snap) is spec.root_styled, (
            f"{spec.id}: root {root} styled={root in snap} under {theme}, expected "
            f"{spec.root_styled}; got {sorted(snap)}"
        )
        snaps[theme] = snap
    assert _distinct(snaps) == 3, f"{spec.id}: stylesheets do not differ across all three themes"
    assert_stylesheet_golden(f"widget.{spec.id}", {"producer": spec.producer, "themes": snaps})


@pytest.mark.ui
@pytest.mark.parametrize("spec", _LIVE_SPECS, ids=[spec.id for spec in _LIVE_SPECS])
def test_widget_stylesheet_follows_live_theme_switch(spec, qapp, qtbot, monkeypatch):
    if spec.setup:
        spec.setup(monkeypatch)
    prune = spec.prune()
    fresh = {}
    for theme in THEMES:
        widget, _tm = _build(spec, theme, qtbot)
        fresh[theme] = widget_stylesheets(widget, prune)

    widget, tm = _build(spec, "bloomberg", qtbot)
    widget.show()
    _drain(qapp)
    assert widget.isVisible()
    for theme in ("dark", "light", "bloomberg"):
        if spec.live == "manager":
            tm.set_theme(theme, save_preference=False)
        else:
            widget.set_theme(theme)
        _drain(qapp)
        live = widget_stylesheets(widget, prune)
        assert live == fresh[theme], (
            f"{spec.id}: stylesheets after switching to {theme!r} differ from a fresh build:\n"
            + _snapshot_diff(fresh[theme], live)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Golden bookkeeping
# ─────────────────────────────────────────────────────────────────────────────


def _expected_golden_names():
    names = {f"service.{row[0]}" for row in SERVICE_QSS_GETTERS}
    names |= {f"service.{method}" for method in SERVICE_VALUE_GETTERS}
    names |= {"chart_theme_service.get_indicator_panel_stylesheet"}
    names |= {f"widget.{spec.id}" for spec in WIDGET_SPECS}
    return names


def test_no_orphan_or_missing_goldens():
    present = {p.stem for p in GOLDEN_DIR.glob("*.json")}
    expected = _expected_golden_names()
    assert present == expected, (
        f"tests/theme/goldens out of sync: orphan={sorted(present - expected)}, "
        f"missing={sorted(expected - present)}"
    )
