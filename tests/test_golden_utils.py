"""Unit tests for tests/golden_utils.py (canonical JSON, goldens, digests, chart snapshots)."""

import datetime as dt
import json
import math

import numpy as np
import pandas as pd
import pytest

import golden_utils as gu
from golden_utils import assert_golden, canonical_json, canonicalize, frame_digest, snapshot_chart


@pytest.fixture
def goldens_dir(tmp_path, monkeypatch):
    """Point golden storage at a temp dir and start in compare mode."""
    d = tmp_path / "goldens"
    monkeypatch.setattr(gu, "GOLDENS_DIR", d)
    monkeypatch.setattr(gu, "UPDATE", False)
    monkeypatch.setattr(gu, "WRITTEN", [])
    return d


# ── canonicalize ─────────────────────────────────────────────────────────────


class TestCanonicalize:
    def test_floats_rounded_to_8_significant_digits(self):
        assert canonicalize(1.23456789123) == 1.2345679
        assert canonicalize(123456789.987) == 123456790.0
        assert canonicalize(0.000123456789123) == 0.00012345679

    def test_nan_inf_and_negative_zero(self):
        assert canonicalize(float("nan")) is None
        assert canonicalize(np.nan) is None
        assert canonicalize(float("inf")) == "inf"
        assert canonicalize(-np.inf) == "-inf"
        assert canonicalize(-0.0) == 0.0 and math.copysign(1, canonicalize(-0.0)) == 1

    def test_numpy_scalars_and_arrays(self):
        assert canonicalize(np.int64(3)) == 3 and isinstance(canonicalize(np.int64(3)), int)
        assert canonicalize(np.float32(0.5)) == 0.5
        assert canonicalize(np.bool_(True)) is True
        assert canonicalize(np.array([1.0, np.nan, 2.0])) == [1.0, None, 2.0]

    def test_timestamps(self):
        assert canonicalize(pd.Timestamp("2026-06-30")) == "2026-06-30"
        assert canonicalize(pd.Timestamp("2026-06-30 12:30")) == "2026-06-30T12:30:00"
        assert canonicalize(dt.date(2020, 1, 2)) == "2020-01-02"
        assert canonicalize(np.datetime64("2021-03-04")) == "2021-03-04"
        assert canonicalize(pd.NaT) is None

    def test_containers_and_keys(self):
        data = {"b": (1, 2), 3: {"z": {4, 2}}, pd.Timestamp("2020-01-01"): None}
        out = canonicalize(data)
        assert out == {"b": [1, 2], "3": {"z": [2, 4]}, "2020-01-01": None}

    def test_dataframe_becomes_digest(self):
        df = pd.DataFrame({"a": [1.0, 2.0]}, index=pd.date_range("2020-01-01", periods=2))
        assert canonicalize(df)["type"] == "DataFrame"

    def test_unknown_type_raises(self):
        with pytest.raises(TypeError):
            canonicalize(object())

    def test_canonical_json_sorted_and_strict(self):
        text = canonical_json({"b": 1, "a": float("nan")})
        assert text.index('"a"') < text.index('"b"')
        assert "NaN" not in text and text.endswith("\n")
        assert json.loads(text) == {"a": None, "b": 1}


# ── assert_golden ────────────────────────────────────────────────────────────


class TestAssertGolden:
    def test_missing_golden_fails(self, goldens_dir):
        with pytest.raises(pytest.fail.Exception, match="golden file missing"):
            assert_golden("demo", {"x": 1}, area="unit")

    def test_update_writes_then_compare_passes(self, goldens_dir):
        assert_golden("demo", {"x": 1.0, "y": [1, 2]}, area="unit", update=True)
        path = goldens_dir / "unit" / "demo.json"
        assert path.exists()
        assert json.loads(path.read_text()) == {"x": 1.0, "y": [1, 2]}
        assert path in gu.WRITTEN
        assert_golden("demo", {"y": [1, 2], "x": 1.0}, area="unit")  # key order irrelevant

    def test_global_update_flag(self, goldens_dir, monkeypatch):
        monkeypatch.setattr(gu, "UPDATE", True)
        assert_golden("flag", [1, 2, 3], area="unit")
        assert (goldens_dir / "unit" / "flag.json").exists()

    def test_update_is_noop_when_equal(self, goldens_dir):
        assert_golden("same", {"a": 1}, area="unit", update=True)
        gu.WRITTEN.clear()
        assert_golden("same", {"a": 1}, area="unit", update=True)
        assert gu.WRITTEN == []

    def test_mismatch_reports_path(self, goldens_dir):
        assert_golden("mm", {"a": {"b": 1.0}, "c": [1, 2]}, area="unit", update=True)
        with pytest.raises(pytest.fail.Exception) as exc:
            assert_golden("mm", {"a": {"b": 2.0}, "c": [1, 2, 3]}, area="unit")
        msg = str(exc.value)
        assert "/a/b: 2.0 != golden 1.0" in msg
        assert "/c: list length 3 != golden 2" in msg

    def test_tiny_float_noise_tolerated(self, goldens_dir):
        assert_golden("tol", {"v": 0.1 + 0.2}, area="unit", update=True)
        assert_golden("tol", {"v": 0.30000000000000004 * (1 + 1e-12)}, area="unit")
        with pytest.raises(pytest.fail.Exception):
            assert_golden("tol", {"v": 0.3001}, area="unit")

    def test_bad_names_rejected(self, goldens_dir):
        with pytest.raises(ValueError):
            assert_golden("../evil", 1, area="unit")
        with pytest.raises(ValueError):
            assert_golden("ok", 1, area="a/b")

    def test_goldens_dir_default_location(self):
        assert gu.golden_path("x", "area").parent.parent.name == "goldens"


# ── frame_digest ─────────────────────────────────────────────────────────────


class TestFrameDigest:
    def test_dataframe_digest(self):
        idx = pd.date_range("2020-01-01", periods=4, freq="MS")
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0, 4.0], "b": [10, 20, 30, 40]}, index=idx)
        d = canonicalize(frame_digest(df))
        assert d["shape"] == [4, 2]
        assert d["columns"] == ["a", "b"]
        assert d["index"]["start"] == "2020-01-01" and d["index"]["end"] == "2020-04-01"
        assert d["index"]["freq"] == "MS"
        a = d["data"]["a"]
        assert (a["count"], a["first"], a["last"], a["sum"]) == (3, 1.0, 4.0, 8.0)
        assert a["first_valid"] == "2020-01-01" and a["last_valid"] == "2020-04-01"
        assert d["data"]["b"]["kind"] == "i"

    def test_inferred_freq_without_explicit_freq(self):
        idx = pd.DatetimeIndex(["2020-01-03", "2020-01-10", "2020-01-17", "2020-01-24"])
        d = frame_digest(pd.Series([1.0, 2, 3, 4], index=idx, name="s"))
        assert d["type"] == "Series" and d["index"]["freq"] == "W-FRI"

    def test_empty_and_none(self):
        assert frame_digest(None) == {"type": "None"}
        d = canonicalize(frame_digest(pd.DataFrame({"a": []}, dtype=float)))
        assert d["shape"] == [0, 1] and d["data"]["a"]["count"] == 0

    def test_multiindex_and_duplicate_columns(self):
        cols = pd.MultiIndex.from_tuples([("Close", "AAPL"), ("Close", "MSFT")])
        df = pd.DataFrame([[1.0, 2.0]], columns=cols)
        assert frame_digest(df)["columns"] == ["Close|AAPL", "Close|MSFT"]
        dup = pd.DataFrame([[1.0, 2.0]], columns=["x", "x"])
        assert set(frame_digest(dup)["data"]) == {"x", "x#1"}

    def test_object_and_bool_columns(self):
        df = pd.DataFrame({"s": ["a", "b", "a"], "f": [True, False, True]})
        d = canonicalize(frame_digest(df))
        assert d["data"]["s"]["n_unique"] == 2
        assert d["data"]["f"]["sum"] == 2

    def test_rejects_other_types(self):
        with pytest.raises(TypeError):
            frame_digest([1, 2])


# ── snapshot_chart / simulate_hover (Qt) ─────────────────────────────────────


def _hover_chart_cls():
    """A tiny test-only BaseChart subclass (independent of app chart modules)."""
    import pyqtgraph as pg
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    from app.ui.widgets.charting.base_chart import BaseChart

    class HoverChart(BaseChart):
        def __init__(self):
            super().__init__()
            self.plot_item = self.addPlot(row=0, col=0)
            self.view_box = self.plot_item.getViewBox()
            self.plot_item.addLegend()
            self._tooltip = self._create_tooltip_label()
            self._placeholder = QLabel("Loading...", self)
            self._placeholder.setAlignment(Qt.AlignCenter)
            self._values = None

        def update_data(self, values):
            self._values = np.asarray(values, dtype=float)
            self.plot_item.clear()
            self.plot_item.plot(np.arange(len(values)), self._values, pen=pg.mkPen((255, 0, 0), width=2),
                                name="Series A")
            self.plot_item.addItem(pg.BarGraphItem(x=[0, 1, 2], height=[1.0, -2.0, 3.0], width=0.5,
                                                   brush=(0, 128, 255, 200)))
            self.plot_item.addItem(pg.InfiniteLine(pos=2.0, angle=0, pen=pg.mkPen((0, 255, 0))))
            txt = pg.TextItem("note")
            self.plot_item.addItem(txt)
            self.plot_item.setXRange(0, len(values) - 1, padding=0)
            self.plot_item.setYRange(-5, 15, padding=0)
            self._placeholder.setVisible(False)

        def _on_mouse_move(self, ev):
            if self._values is None:
                return
            view_pos = self.view_box.mapSceneToView(self.mapToScene(ev.position().toPoint()))
            idx = int(max(0, min(round(view_pos.x()), len(self._values) - 1)))
            self._tooltip.setText(f"<b>idx {idx}</b><br>value: {self._values[idx]:.1f}&nbsp;%")
            self._tooltip.setVisible(True)

    return HoverChart


@pytest.mark.ui
class TestSnapshotChart:
    def test_plot_widget_items(self, qapp):
        import pyqtgraph as pg

        w = pg.PlotWidget()
        w.plot([0, 1, 2], [1.0, np.nan, 3.0], pen=(255, 255, 0), name="yellow")
        w.setXRange(0, 2, padding=0)
        snap = snapshot_chart(w)
        assert snap["type"] == "PlotWidget"
        (plot,) = snap["plots"]
        (item,) = plot["items"]
        assert item["type"] == "PlotDataItem" and item["name"] == "yellow"
        assert item["pen"] == [255, 255, 0, 255]
        assert item["len_x"] == 3 and item["y"]["finite"] == 2 and item["y"]["sum"] == 4.0
        assert plot["view_range"]["x"] == [0.0, 2.0]
        json.dumps(snap)  # fully JSON-serialisable
        w.deleteLater()

    def test_base_chart_snapshot_placeholder_and_items(self, qapp):
        chart = _hover_chart_cls()()
        before = snapshot_chart(chart)
        assert before["placeholder"] == {"text": "Loading...", "shown": True}
        assert before["plots"][0]["items"] == []

        chart.update_data([1.0, 2.0, 4.0, 8.0, 10.0])
        snap = snapshot_chart(chart)
        assert snap["placeholder"]["shown"] is False
        types = [i["type"] for i in snap["plots"][0]["items"]]
        assert types == ["PlotDataItem", "BarGraphItem", "InfiniteLine", "TextItem"]
        line, bars, hline, text = snap["plots"][0]["items"]
        assert line["y"]["sum"] == 25.0 and line["pen"] == [255, 0, 0, 255]
        assert bars["len_x"] == 3 and bars["y"]["sum"] == 2.0 and bars["brush"] == [0, 128, 255, 200]
        assert hline["value"] == 2.0 and hline["angle"] == 0.0
        assert text["text"] == "note"
        assert snap["plots"][0]["legend"]["names"] == ["Series A"]
        assert snap["plots"][0]["view_range"]["y"] == [-5.0, 15.0]
        assert snap["tooltip"] is None
        chart.close()
        chart.deleteLater()

    def test_hover_records_plain_tooltip(self, qapp):
        chart = _hover_chart_cls()()
        chart.update_data([1.0, 2.0, 4.0, 8.0, 10.0])
        snap = snapshot_chart(chart, hover=[0.0, 0.5, 1.0])
        texts = [h["tooltip"] for h in snap["hover"]]
        assert texts == ["idx 0\nvalue: 1.0\xa0%", "idx 2\nvalue: 4.0\xa0%", "idx 4\nvalue: 10.0\xa0%"]
        chart.close()
        chart.deleteLater()

    def test_snapshot_is_deterministic(self, qapp):
        a, b = _hover_chart_cls()(), _hover_chart_cls()()
        for c in (a, b):
            c.update_data([3.0, 1.0, 2.0])
        assert canonical_json(snapshot_chart(a)) == canonical_json(snapshot_chart(b))
        for c in (a, b):
            c.deleteLater()

    def test_html_to_text(self):
        assert gu.html_to_text("<b>Jan 2020</b><br>A: 1&amp;2<br/> ") == "Jan 2020\nA: 1&2"
