"""Chart-module indicator flows through the real widgets (P0.T8, ``ui`` - run with --full).

* Create / edit flows: ``ChartModule._create_custom_indicator`` and
  ``ChartModule._edit_indicator`` driven through the real
  ``CreateIndicatorDialog`` (``nonblocking_dialogs.on_exec`` fills it in and
  clicks its OK button).  The create flow is pinned as a golden: dialog type ->
  registered name, kind, params, overlay/oscillator, default per-line appearance.
* ``PriceChart`` placement and log-scale handling of indicators.
* Known bugs, as strict xfails that assert the CORRECT behaviour:
  - KNOWN-BUG:indicator-volume-edit - editing the built-in Volume indicator
    opens the dialog on "SMA" and replaces Volume with a broken SMA config.
  - KNOWN-BUG:indicator-is-overlay - ``calculate_multiple`` results carry no
    ``is_overlay`` flag, so ``PriceChart.update_indicator_lines`` (live ticks)
    log10-transforms oscillators in Log scale.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

pytestmark = pytest.mark.ui

_TIMER_FLUSH_MS = 150

DIALOG_TYPES_WITHOUT_VOLUME = [
    "SMA", "EMA", "Bollinger Bands", "RSI", "MACD", "ATR", "Stochastic", "OBV", "VWAP",
]


def _dialog_handler(recorder, fill):
    """on_exec: run ``fill(dialog)`` on CreateIndicatorDialog, click OK, return its result code."""
    from app.ui.modules.chart.widgets.create_indicator_dialog import CreateIndicatorDialog

    def on_exec(dialog):
        if not isinstance(dialog, CreateIndicatorDialog):
            return 0
        fill(dialog)
        dialog.create_btn.click()
        return QDialog.result(dialog)  # C++ result code (instance attr ``result`` holds the config)

    recorder.on_exec = on_exec


@pytest.fixture
def chart_module(indicator_service, theme_manager, qtbot):
    """A real ChartModule (not shown, so no data load) on an empty fresh home."""
    from app.ui.modules.chart.chart_module import ChartModule

    module = ChartModule(theme_manager)
    qtbot.addWidget(module)
    yield module
    # PriceChart schedules QTimer.singleShot(50/100 ms) callbacks (resize handle,
    # price label); let them run while the widgets still exist, before qtbot
    # deletes them, so they cannot fire into a later test.
    qtbot.wait(_TIMER_FLUSH_MS)


def _indicator_list_names(module):
    lst = module.indicator_panel.indicator_list
    return [lst.item(i).text() for i in range(lst.count())]


def _create(module, recorder, indicator_type, params=None, custom_name=None):
    def fill(dialog):
        dialog.type_combo.setCurrentText(indicator_type)
        assert dialog.type_combo.currentText() == indicator_type
        for key, value in (params or {}).items():
            dialog.param_inputs[key]["widget"].setText(str(value))
        if custom_name:
            dialog.name_input.setText(custom_name)

    _dialog_handler(recorder, fill)
    module._create_custom_indicator()


def test_create_flow_golden(chart_module, indicator_service, nonblocking_dialogs, fresh_home, chart_golden):
    svc = indicator_service
    before = set(svc.ALL_INDICATORS)
    assert before == {"Volume", "Death/Golden Cross"}

    for indicator_type in DIALOG_TYPES_WITHOUT_VOLUME:
        _create(chart_module, nonblocking_dialogs, indicator_type)
    _create(chart_module, nonblocking_dialogs, "SMA", {"length": 50})
    _create(chart_module, nonblocking_dialogs, "Bollinger Bands", {"length": 10, "std": 2.5})
    _create(chart_module, nonblocking_dialogs, "EMA", {"length": 9}, custom_name="_QT_TEST_fast_ema")

    created = {}
    for name in sorted(set(svc.ALL_INDICATORS) - before):
        config = svc.ALL_INDICATORS[name]
        created[name] = {
            "config": {k: v for k, v in config.items() if k != "per_line_appearance"},
            "per_line_appearance": config.get("per_line_appearance"),
            "is_overlay": svc.is_overlay(name),
        }
    assert len(created) == len(DIALOG_TYPES_WITHOUT_VOLUME) + 3

    # the sidebar list shows them (Volume pinned first) and they are persisted
    assert _indicator_list_names(chart_module) == ["Volume"] + sorted(
        n for n in svc.ALL_INDICATORS if n != "Volume")
    saved = json.loads((fresh_home / ".quant_terminal" / "custom_indicators.json").read_text())
    assert set(created) <= set(saved["overlays"]) | set(saved["oscillators"])

    chart_golden("create_flow", created)


def test_create_duplicate_name_is_rejected(chart_module, indicator_service, nonblocking_dialogs):
    svc = indicator_service
    _create(chart_module, nonblocking_dialogs, "RSI")
    original = svc.ALL_INDICATORS["RSI(14)"]
    nonblocking_dialogs.calls.clear()

    _create(chart_module, nonblocking_dialogs, "RSI")

    assert svc.ALL_INDICATORS["RSI(14)"] is original
    assert ("exec", "CustomMessageBox") in nonblocking_dialogs.calls


def test_volume_settings_via_indicator_dialog(chart_module, indicator_service, nonblocking_dialogs,
                                              fresh_home, restart_indicators):
    """Today the only working way to change Volume settings: pick "Volume" in the dialog."""
    svc = indicator_service

    def fill(dialog):
        dialog.type_combo.setCurrentText("Volume")
        dialog.volume_display_combo.setCurrentText("Line")

    _dialog_handler(nonblocking_dialogs, fill)
    chart_module._create_custom_indicator()

    volume = svc.ALL_INDICATORS["Volume"]
    assert volume["kind"] == "volume" and volume["display_type"] == "line"
    assert svc.is_overlay("Volume") is False
    saved = json.loads((fresh_home / ".quant_terminal" / "volume_settings.json").read_text())
    assert saved["display_type"] == "line"
    assert restart_indicators().ALL_INDICATORS["Volume"]["display_type"] == "line"


def test_edit_flow_changes_params_and_renames(chart_module, indicator_service, nonblocking_dialogs,
                                              fresh_home, restart_indicators):
    svc = indicator_service
    _create(chart_module, nonblocking_dialogs, "SMA")
    _create(chart_module, nonblocking_dialogs, "RSI")
    chart_module.state["indicators"] = ["SMA(20)", "RSI(14)"]

    seen = {}

    def fill(dialog):
        seen["type"] = dialog.type_combo.currentText()
        seen["type_enabled"] = dialog.type_combo.isEnabled()
        seen["length"] = dialog.param_inputs["length"]["widget"].text()
        seen["name"] = dialog.name_input.text()
        seen["lines"] = sorted(dialog.line_widgets)
        dialog.param_inputs["length"]["widget"].setText("50")

    _dialog_handler(nonblocking_dialogs, fill)
    chart_module._edit_indicator("SMA(20)")

    assert seen == {"type": "SMA", "type_enabled": False, "length": "20", "name": "", "lines": ["SMA"]}
    assert "SMA(20)" not in svc.ALL_INDICATORS
    assert svc.ALL_INDICATORS["SMA(50)"]["kind"] == "sma"
    assert svc.ALL_INDICATORS["SMA(50)"]["length"] == 50
    assert svc.is_overlay("SMA(50)") is True
    assert chart_module.state["indicators"] == ["RSI(14)", "SMA(50)"]
    assert "SMA(50)" in _indicator_list_names(chart_module)

    # an oscillator stays an oscillator when edited
    def fill_rsi(dialog):
        dialog.param_inputs["length"]["widget"].setText("7")

    _dialog_handler(nonblocking_dialogs, fill_rsi)
    chart_module._edit_indicator("RSI(14)")
    assert svc.is_overlay("RSI(7)") is False and "RSI(14)" not in svc.ALL_INDICATORS

    reloaded = restart_indicators()
    assert {"SMA(50)", "RSI(7)"} <= set(reloaded.ALL_INDICATORS)
    assert not {"SMA(20)", "RSI(14)"} & set(reloaded.ALL_INDICATORS)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="KNOWN-BUG:indicator-volume-edit editing built-in Volume turns it into a broken SMA")
def test_edit_builtin_volume_keeps_volume(chart_module, indicator_service, nonblocking_dialogs, ohlcv,
                                          restart_indicators):
    """Opening Volume in the edit dialog and pressing OK must leave Volume intact.

    Today: ``indicator_type_map`` has no 'volume', ``findText('volume')`` is -1,
    so the dialog stays on "SMA"; OK returns an SMA config named "Volume" that
    overwrites ALL/OVERLAY_INDICATORS["Volume"] (no 'length' -> calculate()
    returns None) and is persisted as an overlay.  The harness answers only
    ``CreateIndicatorDialog``; if the fix routes Volume to another dialog,
    extend ``_dialog_handler`` accordingly.
    """
    svc = indicator_service
    chart_module.state["indicators"] = ["Volume"]
    seen = {}

    def fill(dialog):
        seen["type"] = dialog.type_combo.currentText()

    _dialog_handler(nonblocking_dialogs, fill)
    chart_module._edit_indicator("Volume")

    problems = []
    if seen.get("type") != "Volume":
        problems.append(f"edit dialog opened on type {seen.get('type')!r}, expected 'Volume'")
    config = svc.ALL_INDICATORS.get("Volume", {})
    if config.get("kind") != "volume":
        problems.append(f"ALL_INDICATORS['Volume'] kind is {config.get('kind')!r}")
    if svc.is_overlay("Volume"):
        problems.append("Volume was registered as an overlay")
    result = svc.calculate(ohlcv, "Volume")
    if result is None or "Volume" not in result.columns:
        problems.append("calculate(df, 'Volume') no longer returns volume data")
    reloaded = restart_indicators()
    if "Volume" in reloaded.get_overlay_names():
        problems.append("after restart Volume is listed as an overlay")
    assert not problems, problems


@pytest.fixture
def price_chart(qapp, qtbot):
    from app.ui.modules.chart.widgets.price_chart import PriceChart

    chart = PriceChart()
    qtbot.addWidget(chart)
    yield chart
    qtbot.wait(_TIMER_FLUSH_MS)  # see chart_module


def _curves(viewbox) -> dict:
    import pyqtgraph as pg

    return {it.name(): it for it in viewbox.addedItems if isinstance(it, pg.PlotCurveItem)}


@pytest.fixture
def log_chart(indicator_service, price_chart, ohlcv):
    svc = indicator_service
    svc.initialize()
    svc.add_custom_indicator("_QT_TEST_SMA20", {"kind": "sma", "length": 20}, is_overlay=True)
    svc.add_custom_indicator("_QT_TEST_RSI14", {"kind": "rsi", "length": 14}, is_overlay=False)
    names = ["_QT_TEST_SMA20", "_QT_TEST_RSI14"]
    price_chart.set_prices(ohlcv, "_QT_TEST_OHLCV", chart_type="Line", scale="Log",
                           indicators=svc.calculate_multiple(ohlcv, names))
    return svc, price_chart, names


def _y(curve):
    return np.asarray(curve.getData()[1], dtype=float)


def test_log_scale_render_places_and_scales_indicators(log_chart, ohlcv):
    svc, chart, _names = log_chart
    price_curves = _curves(chart.price_vb)
    osc_curves = _curves(chart.oscillator_vb)

    assert "SMA" in price_curves and "RSI" not in price_curves
    assert "RSI" in osc_curves and "SMA" not in osc_curves
    sma = svc.calculate(ohlcv, "_QT_TEST_SMA20")["SMA"].to_numpy()
    rsi = svc.calculate(ohlcv, "_QT_TEST_RSI14")["RSI"].to_numpy()
    np.testing.assert_allclose(_y(price_curves["SMA"]), np.log10(sma), rtol=1e-12, equal_nan=True)
    np.testing.assert_allclose(_y(osc_curves["RSI"]), rsi, rtol=1e-12, equal_nan=True)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="KNOWN-BUG:indicator-is-overlay live updates log10 oscillators in Log scale")
def test_live_update_keeps_oscillators_linear_in_log_scale(log_chart, ohlcv):
    """update_indicator_lines (every live tick) must treat oscillators like the full render does.

    Today it reads ``indicator_info.get('is_overlay', True)`` but
    ``IndicatorService.calculate_multiple`` never sets 'is_overlay', so RSI/MACD/
    Stochastic lines get log10-transformed on each tick.
    """
    svc, chart, names = log_chart
    chart.update_indicator_lines(svc.calculate_multiple(ohlcv, names))

    sma = svc.calculate(ohlcv, "_QT_TEST_SMA20")["SMA"].to_numpy()
    np.testing.assert_allclose(_y(_curves(chart.price_vb)["SMA"]), np.log10(sma), rtol=1e-12, equal_nan=True)
    rsi = svc.calculate(ohlcv, "_QT_TEST_RSI14")["RSI"].to_numpy()
    np.testing.assert_allclose(_y(_curves(chart.oscillator_vb)["RSI"]), rsi, rtol=1e-12, equal_nan=True)
