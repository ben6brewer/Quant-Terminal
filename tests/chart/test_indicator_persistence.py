"""Characterization of IndicatorService persistence (P0.T8).

Covers the three JSON files under ``~/.quant_terminal`` (always a per-test
``fresh_home`` here): ``custom_indicators.json``, ``volume_settings.json`` and
``plugin_indicator_appearance.json``.  Saving, an app restart
(``restart_indicators``) and loading must reproduce the registry; a
hand-written legacy file (the format the current code writes, plus the older
entries without ``per_line_appearance``) must keep loading, because saved
settings have to be migrated by any later format change.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from PySide6.QtCore import Qt

PLUGIN_NAME = "Death/Golden Cross"
SAVE_FILE = "custom_indicators.json"
VOLUME_FILE = "volume_settings.json"
PLUGIN_APPEARANCE_FILE = "plugin_indicator_appearance.json"


def _qt_dir(home):
    return home / ".quant_terminal"


def _plain(obj):
    """Tuples -> lists (JSON round-trips tuples as lists); everything else as-is."""
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def _registry(svc) -> dict:
    """Registry as seen through the public API: name lists + config/overlay flag per name."""
    return {
        "overlays": svc.get_overlay_names(),
        "oscillators": svc.get_oscillator_names(),
        "entries": {
            name: {"config": _plain(config), "is_overlay": svc.is_overlay(name)}
            for name, config in svc.ALL_INDICATORS.items()
        },
    }


SMA_APPEARANCE = {
    "SMA": {
        "label": "_QT_TEST Fast SMA",
        "visible": True,
        "color": (0, 150, 255),
        "line_width": 3,
        "line_style": Qt.DashLine,
    }
}
BB_APPEARANCE = {
    "BB_Upper": {"label": "Upper", "visible": True, "color": (255, 100, 100), "line_width": 1,
                 "line_style": Qt.DotLine},
    "BB_Middle": {"label": "", "visible": False, "color": (255, 255, 100), "line_width": 2,
                  "line_style": Qt.SolidLine},
    "BB_Lower": {"label": "Lower", "visible": True, "color": (100, 255, 100), "line_width": 1,
                 "line_style": Qt.DashDotLine},
}
MACD_APPEARANCE = {
    "MACD": {"label": "MACD Line", "visible": True, "color": (0, 150, 255), "line_width": 2,
             "line_style": Qt.SolidLine, "marker_shape": "o", "marker_size": 10},
    "MACDs": {"label": "Signal Line", "visible": True, "color": (255, 150, 0), "line_width": 2,
              "line_style": Qt.DashLine, "marker_shape": "t", "marker_size": 8},
    "MACDh": {"label": "Histogram", "visible": True, "color": (150, 150, 150), "line_width": 1,
              "line_style": Qt.SolidLine, "marker_shape": "s", "marker_size": 6},
}


def _populate(svc):
    """What a user session typically leaves behind: overlays, oscillators, Volume tweaks."""
    svc.initialize()
    svc.add_custom_indicator("_QT_TEST_SMA20", {"kind": "sma", "length": 20,
                                                "per_line_appearance": SMA_APPEARANCE}, is_overlay=True)
    svc.add_custom_indicator("_QT_TEST_BB20", {"kind": "bbands", "length": 20, "std": 2.0,
                                               "per_line_appearance": BB_APPEARANCE}, is_overlay=True)
    svc.add_custom_indicator("_QT_TEST_MACD", {"kind": "macd", "fast": 12, "slow": 26, "signal": 9,
                                               "per_line_appearance": MACD_APPEARANCE}, is_overlay=False)
    svc.add_custom_indicator("_QT_TEST_OBV", {"kind": "obv", "per_line_appearance": {}}, is_overlay=False)
    volume = svc.ALL_INDICATORS["Volume"]
    volume.update({"display_type": "line", "up_color": (1, 2, 3), "down_color": (4, 5, 6)})
    svc.save_volume_settings()
    return svc


def test_initialize_on_empty_home_registers_builtins_only(indicator_service, fresh_home):
    svc = indicator_service
    svc.initialize()

    assert svc.get_all_names() == sorted(["Volume", PLUGIN_NAME])
    assert svc.get_oscillator_names() == ["Volume"]
    assert svc.get_overlay_names() == [PLUGIN_NAME]
    assert svc.ALL_INDICATORS["Volume"] == {
        "kind": "volume",
        "builtin": True,
        "display_type": "histogram",
        "up_color": (76, 153, 0),
        "down_color": (200, 50, 50),
        "line_color": (100, 100, 100),
        "line_width": 2,
    }
    assert svc.ALL_INDICATORS[PLUGIN_NAME] == {"kind": "plugin", "class": PLUGIN_NAME}
    # initialize() only reads: nothing is written to an empty home
    for name in (SAVE_FILE, VOLUME_FILE, PLUGIN_APPEARANCE_FILE):
        assert not (_qt_dir(fresh_home) / name).exists(), name


def test_saved_files_format_golden(indicator_service, fresh_home, chart_golden):
    _populate(indicator_service)
    qt_dir = _qt_dir(fresh_home)
    data = {
        "files": sorted(p.name for p in qt_dir.iterdir()),
        SAVE_FILE: json.loads((qt_dir / SAVE_FILE).read_text()),
        VOLUME_FILE: json.loads((qt_dir / VOLUME_FILE).read_text()),
    }
    # Plugins are never written to custom_indicators.json
    assert PLUGIN_NAME not in data[SAVE_FILE]["overlays"]
    assert PLUGIN_NAME not in data[SAVE_FILE]["oscillators"]
    chart_golden("saved_files", data)


def test_save_restart_load_round_trip(indicator_service, restart_indicators, ohlcv):
    svc = _populate(indicator_service)
    # One entry saved WITHOUT per_line_appearance (older/API-created config)
    svc.add_custom_indicator("_QT_TEST_EMA_LEGACY", {"kind": "ema", "length": 9}, is_overlay=True)
    before = _registry(svc)
    before_results = {n: svc.calculate(ohlcv, n) for n in ("_QT_TEST_SMA20", "_QT_TEST_MACD", "Volume")}

    svc = restart_indicators()
    after = _registry(svc)

    # Loading migrates the entry that had no per_line_appearance to metadata defaults
    migrated = after["entries"]["_QT_TEST_EMA_LEGACY"]["config"].pop("per_line_appearance")
    assert migrated == {"EMA": {"label": "EMA", "visible": True, "color": [255, 150, 0], "line_width": 2,
                                "line_style": Qt.SolidLine, "marker_shape": "o", "marker_size": 10}}
    assert after == before

    # Pen styles come back as Qt.PenStyle (not strings) so pg.mkPen can use them
    sma_style = svc.ALL_INDICATORS["_QT_TEST_SMA20"]["per_line_appearance"]["SMA"]["line_style"]
    assert sma_style == Qt.DashLine and isinstance(sma_style, Qt.PenStyle)
    bb = svc.ALL_INDICATORS["_QT_TEST_BB20"]["per_line_appearance"]
    assert [bb[c]["line_style"] for c in ("BB_Upper", "BB_Middle", "BB_Lower")] == [
        Qt.DotLine, Qt.SolidLine, Qt.DashDotLine]
    assert bb["BB_Middle"]["visible"] is False

    # Volume settings come back from volume_settings.json
    volume = svc.ALL_INDICATORS["Volume"]
    assert volume["display_type"] == "line"
    assert tuple(volume["up_color"]) == (1, 2, 3) and tuple(volume["down_color"]) == (4, 5, 6)
    assert svc.is_overlay("Volume") is False

    # and the reloaded registry calculates identical results
    for name, expected in before_results.items():
        pd.testing.assert_frame_equal(svc.calculate(ohlcv, name), expected)


LEGACY_CUSTOM_INDICATORS = {
    "overlays": {
        "SMA(200)": {"kind": "sma", "length": 200},
        "_QT_TEST_BB": {
            "kind": "bbands",
            "length": 20,
            "std": 2.5,
            "appearance": {"color": [10, 20, 30], "line_style": "dot", "line_width": 1},
        },
        "_QT_TEST_VWAP": {
            "kind": "vwap",
            "per_line_appearance": {
                "VWAP": {"label": "_QT_TEST vwap", "visible": True, "color": [255, 0, 150],
                         "line_width": 2, "line_style": "dashdot", "marker_shape": "o", "marker_size": 10}
            },
        },
    },
    "oscillators": {
        "RSI(14)": {"kind": "rsi", "length": 14},
        "_QT_TEST_STOCH": {
            "kind": "stochastic", "k": 14, "d": 3, "smooth_k": 3,
            "per_line_appearance": {
                "STOCHk": {"label": "%K", "visible": True, "color": [0, 150, 255], "line_width": 2,
                           "line_style": "_qt_test_unknown_style"},
            },
        },
        "Volume": {
            "kind": "volume", "builtin": True, "display_type": "histogram",
            "up_color": [9, 9, 9], "down_color": [8, 8, 8], "line_color": [7, 7, 7], "line_width": 5,
        },
    },
}
LEGACY_VOLUME_SETTINGS = {
    "display_type": "line",
    "up_color": [0, 200, 0],
    "down_color": [200, 0, 0],
    "line_color": [50, 50, 50],
    "line_width": 3,
}


def test_legacy_files_load_and_migrate(indicator_service, fresh_home, ohlcv):
    qt_dir = _qt_dir(fresh_home)
    qt_dir.mkdir(parents=True)
    (qt_dir / SAVE_FILE).write_text(json.dumps(LEGACY_CUSTOM_INDICATORS, indent=2))
    (qt_dir / VOLUME_FILE).write_text(json.dumps(LEGACY_VOLUME_SETTINGS, indent=2))

    svc = indicator_service
    svc.initialize()

    assert svc.get_overlay_names() == sorted(["SMA(200)", "_QT_TEST_BB", "_QT_TEST_VWAP", PLUGIN_NAME])
    assert svc.get_oscillator_names() == sorted(["RSI(14)", "_QT_TEST_STOCH", "Volume"])

    # Missing per_line_appearance -> populated from INDICATOR_COLUMN_METADATA defaults
    sma = svc.ALL_INDICATORS["SMA(200)"]
    assert sma["per_line_appearance"] == {
        "SMA": {"label": "SMA", "visible": True, "color": (0, 150, 255), "line_width": 2,
                "line_style": Qt.SolidLine, "marker_shape": "o", "marker_size": 10}
    }
    bb = svc.ALL_INDICATORS["_QT_TEST_BB"]
    assert list(bb["per_line_appearance"]) == ["BB_Upper", "BB_Middle", "BB_Lower"]
    assert [bb["per_line_appearance"][c]["line_style"] for c in ("BB_Upper", "BB_Middle", "BB_Lower")] == [
        Qt.DashLine, Qt.SolidLine, Qt.DashLine]
    # The legacy global "appearance" dict is kept, with its style string deserialized
    assert bb["appearance"] == {"color": [10, 20, 30], "line_style": Qt.DotLine, "line_width": 1}
    rsi = svc.ALL_INDICATORS["RSI(14)"]["per_line_appearance"]
    assert rsi["RSI"]["color"] == (150, 0, 255)

    # Style strings are deserialized; unknown strings fall back to SolidLine
    vwap_line = svc.ALL_INDICATORS["_QT_TEST_VWAP"]["per_line_appearance"]["VWAP"]
    assert vwap_line["line_style"] == Qt.DashDotLine and vwap_line["label"] == "_QT_TEST vwap"
    stoch = svc.ALL_INDICATORS["_QT_TEST_STOCH"]["per_line_appearance"]
    assert list(stoch) == ["STOCHk"] and stoch["STOCHk"]["line_style"] == Qt.SolidLine

    # Volume: the builtin is re-registered and only volume_settings.json is applied
    # (the Volume colours stored in custom_indicators.json are ignored)
    volume = svc.ALL_INDICATORS["Volume"]
    assert volume["kind"] == "volume" and volume["builtin"] is True
    assert volume["display_type"] == "line"
    assert tuple(volume["up_color"]) == (0, 200, 0)
    assert tuple(volume["down_color"]) == (200, 0, 0)
    assert tuple(volume["line_color"]) == (50, 50, 50)
    assert volume["line_width"] == 3
    assert svc.is_overlay("Volume") is False

    # Every legacy entry still calculates
    for name in ("SMA(200)", "_QT_TEST_BB", "_QT_TEST_VWAP", "RSI(14)", "_QT_TEST_STOCH", "Volume"):
        assert svc.calculate(ohlcv, name) is not None, name


def test_corrupt_indicator_file_loads_as_empty(indicator_service, fresh_home):
    qt_dir = _qt_dir(fresh_home)
    qt_dir.mkdir(parents=True)
    (qt_dir / SAVE_FILE).write_text("{ this is not json")

    svc = indicator_service
    svc.initialize()

    assert svc.get_all_names() == sorted(["Volume", PLUGIN_NAME])
    # the unreadable file is left untouched until the next save
    assert (qt_dir / SAVE_FILE).read_text() == "{ this is not json"


def test_remove_persists_and_protects_builtins(indicator_service, restart_indicators, fresh_home):
    svc = _populate(indicator_service)

    svc.remove_custom_indicator("_QT_TEST_SMA20")
    svc.remove_custom_indicator("_QT_TEST_MACD")
    svc.remove_custom_indicator("Volume")  # builtin: refused
    svc.remove_custom_indicator(PLUGIN_NAME)  # plugin: refused
    svc.remove_custom_indicator("_QT_TEST_never_existed")  # no-op

    expected = sorted(["_QT_TEST_BB20", "_QT_TEST_OBV", "Volume", PLUGIN_NAME])
    assert svc.get_all_names() == expected
    saved = json.loads((_qt_dir(fresh_home) / SAVE_FILE).read_text())
    assert sorted(saved["overlays"]) == ["_QT_TEST_BB20"]
    assert sorted(saved["oscillators"]) == ["Volume", "_QT_TEST_OBV"]

    assert restart_indicators().get_all_names() == expected


def test_plugin_appearance_overrides_round_trip(indicator_service, restart_indicators, fresh_home,
                                                stub_plugin_preview_data, ohlcv):
    svc = indicator_service
    svc.initialize()
    overrides = {
        "SMA50": {"label": "_QT_TEST fifty", "visible": True, "color": (1, 1, 1), "line_width": 4,
                  "line_style": Qt.DashLine},
        "Golden_Cross": {"label": "GC", "visible": True, "color": (0, 255, 0), "line_width": 1,
                         "line_style": Qt.SolidLine, "marker_shape": "star", "marker_size": 14},
        "_QT_TEST_not_a_column": {"label": "dropped", "visible": True, "color": (9, 9, 9)},
    }
    svc.set_plugin_appearance(PLUGIN_NAME, overrides)

    expected = {k: v for k, v in overrides.items() if k != "_QT_TEST_not_a_column"}
    assert svc.get_plugin_appearance(PLUGIN_NAME) == expected
    saved = json.loads((_qt_dir(fresh_home) / PLUGIN_APPEARANCE_FILE).read_text())
    assert list(saved) == [PLUGIN_NAME]
    assert sorted(saved[PLUGIN_NAME]) == ["Golden_Cross", "SMA50"]
    assert saved[PLUGIN_NAME]["SMA50"]["line_style"] == "dash"

    # Unknown plugins are ignored (nothing written for them)
    svc.set_plugin_appearance("_QT_TEST_unknown_plugin", overrides)
    assert "_QT_TEST_unknown_plugin" not in json.loads((_qt_dir(fresh_home) / PLUGIN_APPEARANCE_FILE).read_text())

    svc = restart_indicators()
    assert _plain(svc.get_plugin_appearance(PLUGIN_NAME)) == _plain(expected)
    assert svc.get_plugin_appearance(PLUGIN_NAME)["SMA50"]["line_style"] == Qt.DashLine
    result = svc.calculate_multiple(ohlcv, [PLUGIN_NAME])[PLUGIN_NAME]
    assert _plain(result["per_line_appearance"]) == _plain(expected)

    # Clearing every override removes the plugin entry from the file
    svc.set_plugin_appearance(PLUGIN_NAME, {"_QT_TEST_not_a_column": {}})
    assert svc.get_plugin_appearance(PLUGIN_NAME) == {}
    assert json.loads((_qt_dir(fresh_home) / PLUGIN_APPEARANCE_FILE).read_text()) == {}
