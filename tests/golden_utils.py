"""Golden-file helpers for characterization tests.

Usage::

    from golden_utils import assert_golden, frame_digest, snapshot_chart

    def test_gdp_output(fake_fred):
        result = GdpFredService.fetch_all_data()
        assert_golden("gdp_fetch_all", {k: frame_digest(v) for k, v in result.items()},
                      area="fred_core")

Goldens live in ``tests/goldens/<area>/<name>.json`` as canonical JSON
(sorted keys, floats rounded to 8 significant digits, NaN -> null,
+/-inf -> "inf"/"-inf").  Run pytest with ``--update-goldens`` (or env
``QT_UPDATE_GOLDENS=1``) to (re)write them; without it a missing golden is a
test failure.  Comparison is structural with a small numeric tolerance so
last-bit float noise across platforms does not flake.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import difflib
import enum
import html
import json
import math
import os
import re
from pathlib import Path, PurePath
from typing import Any, Iterable, Optional

GOLDENS_DIR: Path = Path(__file__).resolve().parent / "goldens"
SIG_DIGITS: int = 8
UPDATE: bool = os.environ.get("QT_UPDATE_GOLDENS") == "1"
WRITTEN: list = []  # paths written in this session (reported in the terminal summary)

_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def configure(update: bool) -> None:
    """Called by the root conftest with the ``--update-goldens`` flag."""
    global UPDATE
    UPDATE = bool(update) or os.environ.get("QT_UPDATE_GOLDENS") == "1"


# ─────────────────────────────────────────────────────────────────────────────
# Canonicalization
# ─────────────────────────────────────────────────────────────────────────────


def round_sig(x: float, sig: int = SIG_DIGITS) -> float:
    """Round a finite float to ``sig`` significant digits (and fold -0.0 to 0.0)."""
    if x == 0:
        return 0.0
    r = float(f"{x:.{sig}g}")
    return 0.0 if r == 0 else r


def _canon_float(x: float, sig: int):
    if math.isnan(x):
        return None
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return round_sig(x, sig)


def _canon_timestamp(ts) -> Optional[str]:
    import pandas as pd

    if ts is pd.NaT or (isinstance(ts, float) and math.isnan(ts)):
        return None
    ts = pd.Timestamp(ts)
    if ts is pd.NaT:
        return None
    if ts.tzinfo is None and ts == ts.normalize():
        return ts.strftime("%Y-%m-%d")
    return ts.isoformat()


def _key(k) -> str:
    if isinstance(k, str):
        return k
    c = canonicalize(k)
    return c if isinstance(c, str) else json.dumps(c, sort_keys=True)


def canonicalize(data: Any, sig: int = SIG_DIGITS) -> Any:
    """Convert ``data`` into plain JSON types, deterministically.

    DataFrames/Series become :func:`frame_digest` dicts, numpy arrays/Index
    become lists, timestamps become ISO strings (date-only at midnight), sets
    become sorted lists, Paths become posix strings, enums become ``name``,
    QColor-like objects become ``[r, g, b, a]``.  Unknown types raise TypeError.
    """
    import numpy as np

    if data is None or isinstance(data, (bool, np.bool_)):
        return None if data is None else bool(data)
    if isinstance(data, str):
        return data
    if isinstance(data, (int, np.integer)):
        return int(data)
    if isinstance(data, (float, np.floating)):
        return _canon_float(float(data), sig)
    if isinstance(data, enum.Enum):
        return data.name
    if isinstance(data, PurePath):
        return data.as_posix()

    import pandas as pd

    if isinstance(data, (pd.DataFrame, pd.Series)):
        return canonicalize(frame_digest(data), sig)
    if data is pd.NaT:
        return None
    if isinstance(data, (pd.Timestamp, _dt.datetime, _dt.date, np.datetime64)):
        return _canon_timestamp(data)
    if isinstance(data, (pd.Timedelta, _dt.timedelta, np.timedelta64)):
        return str(pd.Timedelta(data))
    if isinstance(data, pd.Index):
        return [canonicalize(v, sig) for v in data.tolist()]
    if isinstance(data, np.ndarray):
        return [canonicalize(v, sig) for v in data.tolist()]
    if isinstance(data, dict):
        return {_key(k): canonicalize(v, sig) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [canonicalize(v, sig) for v in data]
    if isinstance(data, (set, frozenset)):
        items = [canonicalize(v, sig) for v in data]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True))
    if dataclasses.is_dataclass(data) and not isinstance(data, type):
        return canonicalize(dataclasses.asdict(data), sig)
    if hasattr(data, "getRgb") and callable(data.getRgb):  # QColor
        return list(data.getRgb())
    raise TypeError(
        f"golden_utils.canonicalize: unsupported type {type(data).__name__!r}; "
        "convert it to plain data (or a frame_digest) first"
    )


def canonical_json(data: Any, sig: int = SIG_DIGITS) -> str:
    """Canonical JSON text (sorted keys, 2-space indent, trailing newline)."""
    return json.dumps(canonicalize(data, sig), sort_keys=True, indent=2, ensure_ascii=True,
                      allow_nan=False) + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# Golden assertion
# ─────────────────────────────────────────────────────────────────────────────


def golden_path(name: str, area: str, goldens_dir: Optional[PurePath] = None) -> Path:
    """Path of ``<goldens_dir>/<area>/<name>.json`` (names: ``[A-Za-z0-9_.-]``).

    ``goldens_dir`` defaults to :data:`GOLDENS_DIR` (``tests/goldens``); a test
    directory that keeps its own goldens passes its directory explicitly.
    """
    for part, label in ((name, "name"), (area, "area")):
        if not part or not _NAME_RE.match(part):
            raise ValueError(f"golden {label} must match [A-Za-z0-9_.-]+, got {part!r}")
    root = GOLDENS_DIR if goldens_dir is None else Path(goldens_dir)
    return root / area / f"{name}.json"


def _numbers_close(a, b, rel_tol, abs_tol) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    return math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=abs_tol)


def _diff(a, b, path, out, rel_tol, abs_tol, limit=40):
    if len(out) >= limit:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}/{k}: missing in actual (golden={b[k]!r:.120})")
            elif k not in b:
                out.append(f"{path}/{k}: unexpected in actual (actual={a[k]!r:.120})")
            else:
                _diff(a[k], b[k], f"{path}/{k}", out, rel_tol, abs_tol, limit)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: list length {len(a)} != golden {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out, rel_tol, abs_tol, limit)
        return
    num = (int, float)
    if isinstance(a, num) and isinstance(b, num) and not isinstance(a, bool) and not isinstance(b, bool):
        if not _numbers_close(a, b, rel_tol, abs_tol):
            out.append(f"{path}: {a!r} != golden {b!r}")
        return
    if a != b:
        out.append(f"{path}: {a!r:.200} != golden {b!r:.200}")


def compare_canonical(actual, expected, *, rel_tol: float = 1e-7, abs_tol: float = 1e-12) -> list:
    """Return a list of human-readable differences between two canonical structures."""
    out: list = []
    _diff(actual, expected, "", out, rel_tol, abs_tol)
    return out


def assert_golden(name: str, data: Any, area: str, *, rel_tol: float = 1e-7,
                  abs_tol: float = 1e-12, update: Optional[bool] = None,
                  goldens_dir: Optional[PurePath] = None) -> None:
    """Compare ``data`` with ``<goldens_dir>/<area>/<name>.json``.

    ``goldens_dir`` defaults to ``tests/goldens`` (see :func:`golden_path`).
    With ``--update-goldens`` (or ``update=True``) the file is (re)written and
    the assertion passes.  Otherwise a missing file or any difference fails
    the test with a readable diff.
    """
    import pytest

    path = golden_path(name, area, goldens_dir)
    text = canonical_json(data)
    actual = json.loads(text)
    do_update = UPDATE if update is None else update

    if do_update:
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old is None or compare_canonical(actual, json.loads(old), rel_tol=rel_tol, abs_tol=abs_tol):
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            WRITTEN.append(path)
        return

    if not path.exists():
        pytest.fail(
            f"golden file missing: {path}\nrun pytest with --update-goldens to create it",
            pytrace=False,
        )
    golden_text = path.read_text(encoding="utf-8")
    expected = json.loads(golden_text)
    problems = compare_canonical(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol)
    if problems:
        udiff = "".join(
            list(
                difflib.unified_diff(
                    golden_text.replace("\r\n", "\n").splitlines(True),
                    text.splitlines(True),
                    fromfile=f"golden/{area}/{name}.json",
                    tofile="actual",
                    n=2,
                )
            )[:120]
        )
        pytest.fail(
            f"golden mismatch for {area}/{name} ({len(problems)}+ differences):\n  "
            + "\n  ".join(problems[:40])
            + f"\n--- unified diff (truncated) ---\n{udiff}"
            + "\n(re-run with --update-goldens ONLY in a Behavior-Change commit)",
            pytrace=False,
        )


# ─────────────────────────────────────────────────────────────────────────────
# DataFrame digest
# ─────────────────────────────────────────────────────────────────────────────


def _index_digest(idx) -> dict:
    import pandas as pd

    d = {"type": type(idx).__name__, "len": int(len(idx)), "name": canonicalize(idx.name)
         if not isinstance(idx.name, (list, tuple)) else [str(n) for n in idx.name]}
    if isinstance(idx, pd.MultiIndex):
        d["nlevels"] = idx.nlevels
        d["names"] = [None if n is None else str(n) for n in idx.names]
    if len(idx):
        d["start"] = canonicalize(idx[0]) if not isinstance(idx, pd.MultiIndex) else canonicalize(list(idx[0]))
        d["end"] = canonicalize(idx[-1]) if not isinstance(idx, pd.MultiIndex) else canonicalize(list(idx[-1]))
    else:
        d["start"] = d["end"] = None
    freq = None
    if isinstance(idx, pd.DatetimeIndex):
        freq = idx.freqstr
        if freq is None and len(idx) >= 3:
            try:
                freq = pd.infer_freq(idx)
            except (TypeError, ValueError):
                freq = None
    d["freq"] = freq
    d["monotonic_increasing"] = bool(idx.is_monotonic_increasing)
    d["unique"] = bool(idx.is_unique)
    return d


def _column_digest(s) -> dict:
    import numpy as np
    import pandas as pd

    valid = s.dropna()
    d = {"kind": s.dtype.kind, "count": int(valid.shape[0])}
    if valid.empty:
        d.update(first=None, last=None, first_valid=None, last_valid=None)
        return d
    d["first_valid"] = canonicalize(valid.index[0]) if not isinstance(valid.index, pd.MultiIndex) else None
    d["last_valid"] = canonicalize(valid.index[-1]) if not isinstance(valid.index, pd.MultiIndex) else None
    if pd.api.types.is_bool_dtype(s.dtype):
        d.update(first=bool(valid.iloc[0]), last=bool(valid.iloc[-1]), sum=int(valid.sum()))
    elif pd.api.types.is_numeric_dtype(s.dtype):
        vals = valid.to_numpy(dtype="float64")
        finite = vals[np.isfinite(vals)]
        d.update(
            first=canonicalize(float(vals[0])),
            last=canonicalize(float(vals[-1])),
            sum=canonicalize(float(finite.sum())) if finite.size else None,
            min=canonicalize(float(finite.min())) if finite.size else None,
            max=canonicalize(float(finite.max())) if finite.size else None,
        )
    elif pd.api.types.is_datetime64_any_dtype(s.dtype):
        d.update(first=canonicalize(valid.iloc[0]), last=canonicalize(valid.iloc[-1]))
    else:
        def _plain(v):
            try:
                return canonicalize(v)
            except TypeError:
                return str(v)

        d.update(first=_plain(valid.iloc[0]), last=_plain(valid.iloc[-1]),
                 n_unique=int(valid.astype(str).nunique()))
    return d


def frame_digest(obj) -> dict:
    """Compact, deterministic summary of a DataFrame / Series / None.

    ``{"type", "shape", "columns", "index": {type,len,name,start,end,freq,
    monotonic_increasing,unique}, "data": {col: {kind,count,first,last,
    first_valid,last_valid,sum,min,max}}}`` (numbers rounded on serialisation).
    """
    import pandas as pd

    if obj is None:
        return {"type": "None"}
    kind = type(obj).__name__
    if isinstance(obj, pd.Series):
        df = obj.to_frame(name=obj.name if obj.name is not None else "value")
    elif isinstance(obj, pd.DataFrame):
        df = obj
    else:
        raise TypeError(f"frame_digest expects a DataFrame or Series, got {kind}")
    cols = [_key(c) if not isinstance(c, tuple) else "|".join(str(p) for p in c) for c in df.columns]
    data = {}
    for i, col in enumerate(cols):
        key = col if col not in data else f"{col}#{i}"
        data[key] = _column_digest(df.iloc[:, i])
    return {
        "type": kind,
        "shape": [int(df.shape[0]), int(df.shape[1])] if kind == "DataFrame" else [int(df.shape[0])],
        "columns": cols,
        "index": _index_digest(df.index),
        "data": data,
    }


# ─────────────────────────────────────────────────────────────────────────────
# pyqtgraph chart snapshot
# ─────────────────────────────────────────────────────────────────────────────

_PLACEHOLDER_ATTRS = ("_placeholder", "placeholder", "_placeholder_label", "_empty_label",
                      "_no_data_label", "_message_label")
_TOOLTIP_ATTRS = ("_tooltip", "tooltip", "_tooltip_label", "_hover_label", "_info_label")


def _rgba(obj) -> Optional[list]:
    """RGBA of a pen/brush/colour spec (anything pg.mkPen / mkBrush accepts)."""
    if obj is None:
        return None
    import pyqtgraph as pg
    from PySide6.QtGui import QBrush, QColor, QPen

    try:
        if isinstance(obj, QColor):
            return list(obj.getRgb())
        if isinstance(obj, QPen):
            if obj.style() == 0:  # Qt.NoPen
                return None
            return list(obj.color().getRgb())
        if isinstance(obj, QBrush):
            if obj.style() == 0:  # Qt.NoBrush
                return None
            return list(obj.color().getRgb())
        pen = pg.mkPen(obj)
        return None if pen.style() == 0 else list(pen.color().getRgb())
    except Exception:
        return None


def _brush_rgba(obj) -> Optional[list]:
    if obj is None:
        return None
    import pyqtgraph as pg
    from PySide6.QtGui import QBrush

    try:
        brush = obj if isinstance(obj, QBrush) else pg.mkBrush(obj)
        return None if brush.style() == 0 else list(brush.color().getRgb())
    except Exception:
        return None


def _array_digest(values) -> dict:
    import numpy as np

    if values is None:
        return {"n": 0}
    try:
        arr = np.asarray(values, dtype="float64").ravel()
    except (TypeError, ValueError):
        return {"n": int(len(values))}
    finite = arr[np.isfinite(arr)]
    d = {"n": int(arr.size), "finite": int(finite.size)}
    if finite.size:
        d.update(sum=float(finite.sum()), min=float(finite.min()), max=float(finite.max()),
                 first=float(finite[0]), last=float(finite[-1]))
    return d


def _item_snapshot(item) -> dict:
    import pyqtgraph as pg

    d = {"type": type(item).__name__, "visible": bool(item.isVisible()), "z": float(item.zValue())}
    try:
        if isinstance(item, pg.PlotDataItem):
            d["name"] = item.name()
            d["pen"] = _rgba(item.opts.get("pen"))
            d["fill_brush"] = _brush_rgba(item.opts.get("fillBrush")) if item.opts.get("fillLevel") is not None else None
            d["symbol"] = item.opts.get("symbol") if isinstance(item.opts.get("symbol"), (str, type(None))) else "custom"
            x, y = item.xData, item.yData
            d["len_x"] = 0 if x is None else int(len(x))
            d["x"] = _array_digest(x)
            d["y"] = _array_digest(y)
        elif isinstance(item, pg.PlotCurveItem):
            d["name"] = item.name()
            d["pen"] = _rgba(item.opts.get("pen"))
            d["brush"] = _brush_rgba(item.opts.get("brush"))
            d["len_x"] = 0 if item.xData is None else int(len(item.xData))
            d["x"] = _array_digest(item.xData)
            d["y"] = _array_digest(item.yData)
        elif isinstance(item, pg.ScatterPlotItem):
            d["name"] = item.name()
            data = item.data
            d["len_x"] = int(len(data))
            d["x"] = _array_digest(data["x"] if len(data) else [])
            d["y"] = _array_digest(data["y"] if len(data) else [])
        elif isinstance(item, pg.BarGraphItem):
            o = item.opts
            x = o.get("x") if o.get("x") is not None else o.get("x0")
            h = o.get("height")
            if h is None and o.get("y1") is not None:
                h = o.get("y1")
            d["name"] = o.get("name")
            d["len_x"] = 0 if x is None else int(len(x))
            d["x"] = _array_digest(x)
            d["y"] = _array_digest(h)
            d["y0"] = _array_digest(o.get("y0")) if o.get("y0") is not None and not isinstance(o.get("y0"), (int, float)) else o.get("y0")
            brushes = o.get("brushes")
            if brushes is not None:
                d["brushes"] = sorted({tuple(_brush_rgba(b) or ()) for b in brushes})
            d["brush"] = _brush_rgba(o.get("brush"))
            d["pen"] = _rgba(o.get("pen"))
        elif isinstance(item, pg.InfiniteLine):
            d["angle"] = float(item.angle)
            d["value"] = float(item.value())
            d["pen"] = _rgba(item.pen)
            label = getattr(item, "label", None)
            if label is not None:
                d["label"] = label.toPlainText()
        elif isinstance(item, pg.TextItem):
            d["text"] = item.toPlainText()
            d["color"] = _rgba(item.color)
        elif isinstance(item, pg.LinearRegionItem):
            d["region"] = [float(v) for v in item.getRegion()]
            d["brush"] = _brush_rgba(item.brush)
        elif isinstance(item, pg.FillBetweenItem):
            d["brush"] = _brush_rgba(item.brush())
    except Exception as exc:  # never let a snapshot crash the test
        d["error"] = f"{type(exc).__name__}: {exc}"
    return d


def _layout_plot_items(layout) -> list:
    import pyqtgraph as pg

    found = []
    for row in sorted(layout.rows):
        for col in sorted(layout.rows[row]):
            it = layout.rows[row][col]
            if isinstance(it, pg.PlotItem):
                found.append(it)
            elif isinstance(it, pg.GraphicsLayout):
                found.extend(_layout_plot_items(it))
    return found


def find_plot_items(chart) -> list:
    """All PlotItems of a PlotItem / PlotWidget / GraphicsLayoutWidget / container QWidget."""
    import pyqtgraph as pg

    if isinstance(chart, pg.PlotItem):
        return [chart]
    if isinstance(chart, pg.PlotWidget):
        return [chart.getPlotItem()]
    if isinstance(chart, pg.GraphicsLayoutWidget):
        items = _layout_plot_items(chart.ci)
        pi = getattr(chart, "plot_item", None)
        if isinstance(pi, pg.PlotItem) and pi not in items:
            items.insert(0, pi)
        return items
    from PySide6.QtWidgets import QWidget

    if isinstance(chart, QWidget):
        out = []
        for view in chart.findChildren(pg.GraphicsView):
            for pi in find_plot_items(view):
                if pi not in out:
                    out.append(pi)
        return out
    raise TypeError(f"snapshot_chart: unsupported chart type {type(chart).__name__}")


def _axis_snapshot(pi, name) -> Optional[dict]:
    try:
        ax = pi.getAxis(name)
    except Exception:
        return None
    return {
        "visible": bool(ax.isVisible()),
        "label": ax.labelText or "",
        "units": ax.labelUnits or "",
        "grid": ax.grid if isinstance(ax.grid, (bool, int, float)) else None,
    }


def _plot_snapshot(pi) -> dict:
    vr = pi.vb.viewRange()
    legend = None
    if getattr(pi, "legend", None) is not None:
        legend = {
            "visible": bool(pi.legend.isVisible()),
            "names": [lbl.text for _sample, lbl in pi.legend.items],
        }
    title = pi.titleLabel.text if pi.titleLabel is not None and pi.titleLabel.isVisible() else ""
    return {
        "title": title,
        "view_range": {"x": [float(vr[0][0]), float(vr[0][1])], "y": [float(vr[1][0]), float(vr[1][1])]},
        "axes": {n: _axis_snapshot(pi, n) for n in ("left", "bottom", "right", "top")},
        "legend": legend,
        "items": [_item_snapshot(it) for it in pi.items],
    }


def _extra_viewboxes(chart, plot_items) -> list:
    """ViewBoxes in the scene that belong to no PlotItem (e.g. secondary y axes)."""
    import pyqtgraph as pg

    scene = None
    if isinstance(chart, pg.GraphicsView):
        scene = chart.scene()
    elif plot_items:
        scene = plot_items[0].scene()
    if scene is None:
        return []
    own = {id(pi.vb) for pi in plot_items}
    out = []
    for it in scene.items():
        if isinstance(it, pg.ViewBox) and id(it) not in own:
            if any(id(it) == id(getattr(p, "vb", None)) for p in plot_items):
                continue
            out.append(it)
    snaps = []
    for vb in out:
        vr = vb.viewRange()
        snaps.append({
            "view_range": {"x": [float(vr[0][0]), float(vr[0][1])], "y": [float(vr[1][0]), float(vr[1][1])]},
            "items": [_item_snapshot(i) for i in vb.addedItems],
        })
    snaps.sort(key=lambda s: json.dumps(canonicalize(s), sort_keys=True))
    return snaps


def html_to_text(text: str) -> str:
    """Strip rich-text markup (``<br>`` -> newline) and unescape entities."""
    text = re.sub(r"(?i)<br\s*/?>", "\n", text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def _find_label(chart, names: Iterable[str]):
    from PySide6.QtWidgets import QLabel

    for n in names:
        w = getattr(chart, n, None)
        if isinstance(w, QLabel):
            return w
    return None


def tooltip_text(chart) -> Optional[str]:
    """Plain text of the chart's hover tooltip QLabel if it is shown, else None."""
    label = _find_label(chart, _TOOLTIP_ATTRS)
    if label is None or label.isHidden():
        return None
    return html_to_text(label.text())


def simulate_hover(chart, x_frac: float = 0.5, y_frac: float = 0.5, *, plot_item=None,
                   size=(1200, 700)) -> Optional[str]:
    """Move the mouse to a fraction of the (first) plot's view range; return tooltip text.

    Shows/resizes the chart if needed (offscreen), sends a synthetic
    ``MouseMove`` to the view and emits ``scene().sigMouseMoved``.
    """
    import pyqtgraph as pg
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    items = find_plot_items(chart)
    pi = plot_item or (items[0] if items else None)
    if pi is None:
        return None
    if chart.width() < 100 or chart.height() < 100:
        chart.resize(*size)
    if not chart.isVisible():
        chart.show()
    QApplication.processEvents()
    (x0, x1), (y0, y1) = pi.vb.viewRange()
    scene_pt = pi.vb.mapViewToScene(QPointF(x0 + x_frac * (x1 - x0), y0 + y_frac * (y1 - y0)))
    view = chart if isinstance(chart, pg.GraphicsView) else pi.scene().views()[0]
    local = view.mapFromScene(scene_pt)
    ev = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(local),
        QPointF(view.mapToGlobal(local)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseMoveEvent(ev)
    try:
        pi.scene().sigMouseMoved.emit(scene_pt)
    except Exception:
        pass
    QApplication.processEvents()
    return tooltip_text(chart)


def snapshot_chart(chart, *, hover: Optional[Iterable[float]] = None) -> dict:
    """Deterministic structural snapshot of a pyqtgraph chart.

    Records, per PlotItem: title, view ranges, axes (label/visible/grid),
    legend names and every item (type, name, pen/brush RGBA, len(x), x/y
    digests incl. checksum = finite sum); plus secondary ViewBoxes, the
    placeholder label (text + shown) and the tooltip.  ``hover`` is an
    optional list of x-fractions (0..1) of the first plot's x range at which
    to simulate a mouse move; each result is recorded under ``"hover"``.
    """
    plot_items = find_plot_items(chart)
    snap = {
        "type": type(chart).__name__,
        "theme": getattr(chart, "_theme", None) if isinstance(getattr(chart, "_theme", None), str) else None,
        "plots": [_plot_snapshot(pi) for pi in plot_items],
        "extra_viewboxes": _extra_viewboxes(chart, plot_items),
    }
    try:
        bg = chart.backgroundBrush()
        snap["background"] = list(bg.color().getRgb()) if bg.style() != 0 else None
    except Exception:
        snap["background"] = None
    ph = _find_label(chart, _PLACEHOLDER_ATTRS)
    snap["placeholder"] = None if ph is None else {"text": ph.text(), "shown": not ph.isHidden()}
    snap["tooltip"] = tooltip_text(chart)
    if hover:
        snap["hover"] = [{"at": float(f), "tooltip": simulate_hover(chart, f)} for f in hover]
    return canonicalize(snap)
