"""Characterization of ``IndicatorService.calculate`` for every indicator type (P0.T8).

Every built-in ``kind`` (sma, ema, bbands, rsi, macd, atr, stochastic, obv,
vwap, volume) plus the bundled ``Death/Golden Cross`` plugin is calculated on
the deterministic ``ohlcv`` frame and pinned as a golden digest
(``tests/chart/goldens/indicators/``).  Parameters mirror the defaults of
``CreateIndicatorDialog.INDICATOR_TYPES``, plus a few non-default variants so
parameter plumbing is covered too.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from golden_utils import frame_digest

pytestmark = pytest.mark.golden

# (registered name, config without per_line_appearance, expected overlay flag)
BUILTIN_CASES = [
    ("_QT_TEST_SMA20", {"kind": "sma", "length": 20}, True),
    ("_QT_TEST_SMA50", {"kind": "sma", "length": 50}, True),
    ("_QT_TEST_EMA12", {"kind": "ema", "length": 12}, True),
    ("_QT_TEST_EMA26", {"kind": "ema", "length": 26}, True),
    ("_QT_TEST_BB20_2", {"kind": "bbands", "length": 20, "std": 2.0}, True),
    ("_QT_TEST_BB10_2.5", {"kind": "bbands", "length": 10, "std": 2.5}, True),
    ("_QT_TEST_RSI14", {"kind": "rsi", "length": 14}, False),
    ("_QT_TEST_RSI7", {"kind": "rsi", "length": 7}, False),
    ("_QT_TEST_MACD12_26_9", {"kind": "macd", "fast": 12, "slow": 26, "signal": 9}, False),
    ("_QT_TEST_MACD5_35_5", {"kind": "macd", "fast": 5, "slow": 35, "signal": 5}, False),
    ("_QT_TEST_ATR14", {"kind": "atr", "length": 14}, False),
    ("_QT_TEST_STOCH14_3_3", {"kind": "stochastic", "k": 14, "d": 3, "smooth_k": 3}, False),
    ("_QT_TEST_STOCH5_5_1", {"kind": "stochastic", "k": 5, "d": 5, "smooth_k": 1}, False),
    ("_QT_TEST_OBV", {"kind": "obv"}, False),
    ("_QT_TEST_VWAP", {"kind": "vwap"}, True),
]

BUILTIN_KINDS = {"sma", "ema", "bbands", "rsi", "macd", "atr", "stochastic", "obv", "vwap", "volume"}
PLUGIN_NAME = "Death/Golden Cross"

# Row positions sampled verbatim into the golden (warm-up edges, flat bars, tail).
SAMPLE_POSITIONS = (0, 1, 4, 5, 9, 10, 13, 14, 19, 20, 25, 33, 37, 49, 50, 100, 199, 200, 211, 333, 518, 519)


def _samples(df: pd.DataFrame) -> dict:
    out = {}
    for pos in SAMPLE_POSITIONS:
        row = df.iloc[pos]
        out[f"{pos:03d}@{df.index[pos].date().isoformat()}"] = [
            None if pd.isna(v) else float(v) for v in row.tolist()
        ]
    return out


def _entry(svc, name: str, df: pd.DataFrame) -> dict:
    result = svc.calculate(df, name)
    assert result is not None, f"calculate({name!r}) returned None"
    assert isinstance(result, pd.DataFrame)
    assert result.index.equals(df.index), f"{name}: result index differs from input index"
    config = {k: v for k, v in svc.ALL_INDICATORS[name].items() if k != "per_line_appearance"}
    return {
        "config": config,
        "is_overlay": svc.is_overlay(name),
        "columns": list(result.columns),
        "dtypes": [str(t) for t in result.dtypes],
        "digest": frame_digest(result),
        "samples": _samples(result),
    }


@pytest.fixture
def registered(indicator_service):
    """Initialized service with one indicator registered per BUILTIN_CASES row."""
    svc = indicator_service
    svc.initialize()
    for name, config, overlay in BUILTIN_CASES:
        svc.add_custom_indicator(name, dict(config), is_overlay=overlay)
    return svc


def test_every_builtin_kind_is_covered():
    """Guard: the golden covers every kind the calculate() dispatch knows today."""
    from app.ui.modules.chart.services.indicator_service import IndicatorService

    covered = {cfg["kind"] for _, cfg, _ in BUILTIN_CASES} | {"volume"}
    assert covered == BUILTIN_KINDS
    assert set(IndicatorService.INDICATOR_COLUMN_METADATA) == BUILTIN_KINDS


def test_input_frame_is_deterministic(ohlcv, chart_golden):
    """Pin the input frame itself so a fixture change is not mistaken for an indicator change."""
    assert len(ohlcv) == 520
    direction = np.sign(ohlcv["Close"] - ohlcv["Open"])
    assert set(direction.unique()) == {-1.0, 0.0, 1.0}
    chart_golden("input_ohlcv", {"digest": frame_digest(ohlcv), "samples": _samples(ohlcv)})


def test_calculate_builtin_indicators_golden(registered, ohlcv, chart_golden):
    svc = registered
    data = {name: _entry(svc, name, ohlcv) for name, _, _ in BUILTIN_CASES}
    data["Volume"] = _entry(svc, "Volume", ohlcv)
    chart_golden("calculate_builtin", data)


def test_calculate_plugin_indicator_golden(registered, ohlcv, chart_golden):
    svc = registered
    assert PLUGIN_NAME in svc.CUSTOM_INDICATOR_CLASSES
    entry = _entry(svc, PLUGIN_NAME, ohlcv)
    result = svc.calculate(ohlcv, PLUGIN_NAME)
    entry["crossings"] = {
        col: [d.date().isoformat() for d in result.index[result[col].notna()]]
        for col in ("Golden_Cross", "Death_Cross")
    }
    assert entry["crossings"]["Golden_Cross"] or entry["crossings"]["Death_Cross"], (
        "fixture frame should contain at least one 50/200 crossover"
    )
    chart_golden("calculate_plugin_death_golden_cross", entry)


def test_output_columns_match_column_metadata(registered, ohlcv):
    """calculate() columns == INDICATOR_COLUMN_METADATA columns (+ Volume_Direction for Volume)."""
    svc = registered
    for name, config, _ in BUILTIN_CASES + [("Volume", {"kind": "volume"}, False)]:
        result = svc.calculate(ohlcv, name)
        expected = [m["column"] for m in svc.get_column_metadata(name)]
        if config["kind"] == "volume":
            expected = expected + ["Volume_Direction"]
        assert list(result.columns) == expected, name
        assert svc.preview_indicator_columns(name) == [m["column"] for m in svc.get_column_metadata(name)]


def test_indicator_identities(registered, ohlcv):
    """Cross-checks between indicators (independent of the golden numbers)."""
    svc = registered
    close = ohlcv["Close"]

    sma = svc.calculate(ohlcv, "_QT_TEST_SMA20")["SMA"]
    bb = svc.calculate(ohlcv, "_QT_TEST_BB20_2")
    pd.testing.assert_series_equal(bb["BB_Middle"], sma, check_names=False)
    width = (bb["BB_Upper"] - bb["BB_Lower"]).dropna()
    expected_width = (4.0 * close.rolling(20).std()).dropna()
    np.testing.assert_allclose(width.to_numpy(), expected_width.to_numpy(), rtol=1e-10)
    assert sma.isna().sum() == 19 and sma.notna().iloc[19:].all()

    macd = svc.calculate(ohlcv, "_QT_TEST_MACD12_26_9")
    np.testing.assert_allclose(macd["MACDh"], macd["MACD"] - macd["MACDs"], rtol=0, atol=1e-12)

    rsi = svc.calculate(ohlcv, "_QT_TEST_RSI14")["RSI"].dropna()
    assert ((rsi >= 0) & (rsi <= 100)).all()
    stoch = svc.calculate(ohlcv, "_QT_TEST_STOCH14_3_3").dropna()
    assert ((stoch >= 0) & (stoch <= 100)).all().all()

    atr = svc.calculate(ohlcv, "_QT_TEST_ATR14")["ATR"]
    assert atr.notna().all() and (atr > 0).all()

    obv = svc.calculate(ohlcv, "_QT_TEST_OBV")["OBV"]
    assert obv.iloc[0] == 0
    step = obv.diff().iloc[1:]
    direction = np.sign(close.diff()).iloc[1:]
    np.testing.assert_array_equal(step.to_numpy(), (direction * ohlcv["Volume"].iloc[1:]).to_numpy())

    vwap = svc.calculate(ohlcv, "_QT_TEST_VWAP")["VWAP"]
    typical = (ohlcv["High"] + ohlcv["Low"] + ohlcv["Close"]) / 3
    assert vwap.iloc[0] == pytest.approx(typical.iloc[0])

    volume = svc.calculate(ohlcv, "Volume")
    pd.testing.assert_series_equal(volume["Volume"], ohlcv["Volume"])
    flat = ohlcv["Close"] == ohlcv["Open"]
    assert flat.sum() >= 2
    assert (volume.loc[flat, "Volume_Direction"] == 0).all()
    assert (volume.loc[ohlcv["Close"] > ohlcv["Open"], "Volume_Direction"] == 1).all()
    assert (volume.loc[ohlcv["Close"] < ohlcv["Open"], "Volume_Direction"] == -1).all()


def test_calculate_failure_modes_return_none(registered, ohlcv):
    """Unknown names, missing params, unknown kinds and missing Volume -> None (never raise)."""
    svc = registered
    assert svc.calculate(ohlcv, "_QT_TEST_not_registered") is None

    svc.ALL_INDICATORS["_QT_TEST_SMA_NO_LENGTH"] = {"kind": "sma"}
    assert svc.calculate(ohlcv, "_QT_TEST_SMA_NO_LENGTH") is None
    svc.ALL_INDICATORS["_QT_TEST_UNKNOWN_KIND"] = {"kind": "_qt_test_kind"}
    assert svc.calculate(ohlcv, "_QT_TEST_UNKNOWN_KIND") is None

    no_volume = ohlcv.drop(columns=["Volume"])
    for name in ("_QT_TEST_OBV", "_QT_TEST_VWAP", "Volume"):
        assert svc.calculate(no_volume, name) is None, name
    assert svc.calculate(no_volume, "_QT_TEST_SMA20") is not None


def test_calculate_multiple_contract(registered, ohlcv):
    """calculate_multiple: skips failures, returns data + per_line_appearance per name."""
    svc = registered
    appearance = {"SMA": {"label": "_QT_TEST_label", "visible": True, "color": (1, 2, 3)}}
    svc.ALL_INDICATORS["_QT_TEST_SMA20"]["per_line_appearance"] = appearance

    names = ["_QT_TEST_SMA20", "_QT_TEST_RSI14", "Volume", PLUGIN_NAME, "_QT_TEST_missing"]
    out = svc.calculate_multiple(ohlcv, names)

    assert list(out) == ["_QT_TEST_SMA20", "_QT_TEST_RSI14", "Volume", PLUGIN_NAME]
    for name, info in out.items():
        assert {"data", "per_line_appearance"} <= set(info), name
        pd.testing.assert_frame_equal(info["data"], svc.calculate(ohlcv, name))
    assert out["_QT_TEST_SMA20"]["per_line_appearance"] == appearance
    assert out["_QT_TEST_RSI14"]["per_line_appearance"] == {}
    assert out[PLUGIN_NAME]["per_line_appearance"] == {}


def test_overlay_oscillator_classification(registered):
    svc = registered
    expected_overlays = sorted([n for n, _, o in BUILTIN_CASES if o] + [PLUGIN_NAME])
    expected_oscillators = sorted([n for n, _, o in BUILTIN_CASES if not o] + ["Volume"])
    assert svc.get_overlay_names() == expected_overlays
    assert svc.get_oscillator_names() == expected_oscillators
    assert svc.get_all_names() == sorted(expected_overlays + expected_oscillators)
    assert svc.is_overlay(PLUGIN_NAME) is True
    assert svc.is_overlay("Volume") is False
    assert svc.get_column_metadata(PLUGIN_NAME) is None
    assert svc.get_column_metadata("_QT_TEST_not_registered") == []
