"""Shared harness for the hub smoke test and the visual capture (tests/visual).

What it provides:

* :func:`build_hub_like_main` runs the REAL ``app.main.main()`` with the Qt
  event loop shimmed out (``QApplication(...)`` stands for the session app,
  ``exec()`` returns 0 immediately, and SIGINT wiring is skipped), and returns
  the ``HubWindow`` it built.  Registration, theme loading, show and maximize
  all run exactly as in the app.
* :class:`ActivityTracker` records every ``QThread.start()`` /
  ``threading.Thread.start()`` and every ``CalculationWorker`` error, so that
  :meth:`ActivityTracker.wait_idle` can wait (bounded) until a module's
  background work and its queued completion callbacks have finished.
* :class:`ErrorCapture` records uncaught exceptions (``sys.excepthook``,
  ``threading.excepthook``, ``sys.unraisablehook``), Qt messages
  (``qInstallMessageHandler``) and log records at WARNING or above.
* :func:`seed_offline_caches` writes the one cache the fakes cannot serve:
  the stock-heatmap constituent list (normally scraped from Wikipedia).
* :class:`FrozenClock` freezes ``datetime``, ``pandas.Timestamp.now/today`` and
  ``QDate/QDateTime`` "now" at :data:`FROZEN_NOW` (the fakes' last day).

Everything here is test code.  Nothing in ``src`` is modified.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sys
import threading
import time
import traceback
import types
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

THEMES: Tuple[str, ...] = ("dark", "light", "bloomberg")

# Fakes end on 2026-06-30 (a Tuesday).  22:00 local is after the US close, so
# market-hours logic sees a closed market and no stock polling starts.
FROZEN_NOW = _dt.datetime(2026, 6, 30, 22, 0, 0)
FROZEN_TZ = "America/New_York"

# Qt message fragments that indicate real threading/lifetime bugs even though
# Qt reports them only as warnings.
QT_WARNING_ERRORS: Tuple[str, ...] = (
    "Cannot create children for a parent that is in a different thread",
    "Timers cannot be started from another thread",
    "Timers cannot be stopped from another thread",
    "Destroyed while thread is still running",
    "Cannot send events to objects owned by a different thread",
    "Cannot move objects with a parent",
)

TRACEBACK_MARKER = "Traceback (most recent call last)"


# ─────────────────────────────────────────────────────────────────────────────
# Fonts (offscreen platform)
# ─────────────────────────────────────────────────────────────────────────────

# The font helpers live in fixtures.qt_fonts (the root conftest's qapp fixture
# uses them too); re-exported here for the smoke and visual tests.
from fixtures.qt_fonts import (  # noqa: E402,F401
    APP_FONT,
    FONT_SUBSTITUTIONS,
    ensure_fonts,
    pin_app_font,
)


# ─────────────────────────────────────────────────────────────────────────────
# Registry helpers
# ─────────────────────────────────────────────────────────────────────────────


def registered_entries() -> List[dict]:
    """Every entry of ``app.core.config.MODULE_SECTIONS`` (the list ``main()`` registers)."""
    from app.core.config import MODULE_SECTIONS

    return [entry for section in MODULE_SECTIONS.values() for entry in section]


def registered_module_ids() -> List[str]:
    return [entry["id"] for entry in registered_entries()]


# ─────────────────────────────────────────────────────────────────────────────
# Building the hub exactly like app.main.main()
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MainRun:
    hub: Any
    theme_manager: Any
    return_code: int
    exec_calls: int
    log_handlers: List[logging.Handler]  # root-logger handlers main() added


def build_hub_like_main(monkeypatch) -> MainRun:
    """Run ``app.main.main()`` without entering the event loop; return the hub it built.

    ``main()`` itself is unchanged: only ``QApplication`` (-> a shim over the
    session app whose ``exec()`` returns 0 at once) and ``signal`` (no
    process-wide SIGINT handler) are swapped in its namespace.  The hub is
    found where ``main()`` would enter the event loop: the new visible
    ``HubWindow`` among the application's top-level widgets.  A reference is
    taken there, because ``main()`` returning drops its own.
    """
    import signal as _signal

    import app.main as main_mod
    from PySide6.QtWidgets import QApplication

    from app.ui.hub_window import HubWindow

    real_app = QApplication.instance()
    assert real_app is not None, "request the qapp fixture before building the hub"
    before = list(real_app.topLevelWidgets())
    captured: Dict[str, Any] = {"hubs": [], "exec_calls": 0}

    class _AppShim:
        """Stands in for ``QApplication``: the session app, no event loop."""

        def __init__(self, argv=None):
            self.argv = argv

        @classmethod
        def instance(cls):
            return cls()

        def exec(self):
            captured["exec_calls"] += 1
            captured["hubs"] = [
                w for w in real_app.topLevelWidgets()
                if isinstance(w, HubWindow) and w.isVisible() and not any(w is b for b in before)
            ]
            return 0

        exec_ = exec

        def quit(self):
            pass

        def __getattr__(self, name):
            return getattr(real_app, name)

    monkeypatch.setattr(main_mod, "QApplication", _AppShim)
    # main() installs a process-wide SIGINT handler; keep pytest's.
    monkeypatch.setattr(
        main_mod,
        "signal",
        types.SimpleNamespace(signal=lambda *a, **k: None, SIGINT=_signal.SIGINT),
    )

    root = logging.getLogger()
    handlers_before = list(root.handlers)
    rc = main_mod.main()
    added = [h for h in root.handlers if h not in handlers_before]
    assert len(captured["hubs"]) == 1, f"main() showed {len(captured['hubs'])} new HubWindows"
    hub = captured["hubs"][0]
    return MainRun(hub=hub, theme_manager=hub.theme_manager, return_code=rc,
                   exec_calls=captured["exec_calls"], log_handlers=added)


def close_hub(hub, qapp, run: Optional[MainRun] = None) -> None:
    """Delete the hub (and every cached module); undo main()'s logging handlers."""
    from PySide6.QtCore import QCoreApplication, QEvent

    if run is not None:
        root = logging.getLogger()
        for handler in run.log_handlers:
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:  # pragma: no cover - best effort
                pass
    try:
        hub.hide()
        hub.close()
        hub.deleteLater()
    except RuntimeError:
        return
    for _ in range(3):
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qapp.processEvents()


# ─────────────────────────────────────────────────────────────────────────────
# Offline caches the fakes cannot provide
# ─────────────────────────────────────────────────────────────────────────────

# (ticker, name, sector, sub_industry) - _QT_TEST_ names, served by FakeYahoo.
HEATMAP_CONSTITUENTS: Tuple[Tuple[str, str, str, str], ...] = (
    ("_QT_TEST_TEC1", "_QT_TEST Tech One", "Information Technology", "Software"),
    ("_QT_TEST_TEC2", "_QT_TEST Tech Two", "Information Technology", "Semiconductors"),
    ("_QT_TEST_TEC3", "_QT_TEST Tech Three", "Information Technology", "Hardware"),
    ("_QT_TEST_FIN1", "_QT_TEST Bank One", "Financials", "Banks"),
    ("_QT_TEST_FIN2", "_QT_TEST Bank Two", "Financials", "Insurance"),
    ("_QT_TEST_HLT1", "_QT_TEST Health One", "Health Care", "Pharmaceuticals"),
    ("_QT_TEST_HLT2", "_QT_TEST Health Two", "Health Care", "Biotechnology"),
    ("_QT_TEST_ENE1", "_QT_TEST Energy One", "Energy", "Oil & Gas"),
    ("_QT_TEST_IND1", "_QT_TEST Industrial One", "Industrials", "Aerospace"),
    ("_QT_TEST_CON1", "_QT_TEST Consumer One", "Consumer Staples", "Beverages"),
)


def seed_offline_caches() -> List[Path]:
    """Write the stock-heatmap constituent caches (all 3 markets); return the paths.

    ``SP500HeatmapService`` scrapes Wikipedia (blocked by the network guard)
    unless ``<cache>/heatmap_<key>.json`` is younger than 7 days.  Paths are
    read from the service module at call time, so this must run after the
    ``fresh_home`` fixture.
    """
    import pandas as pd

    from app.ui.modules.stock_heatmap.services import sp500_heatmap_service as svc

    df = pd.DataFrame(HEATMAP_CONSTITUENTS, columns=["ticker", "name", "sector", "sub_industry"])
    svc._CACHE_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for key in ("sp500", "nasdaq100", "dow30"):
        path = svc._CACHE_DIR / f"heatmap_{key}.json"
        df.to_json(path)
        written.append(path)
    # Drop any in-memory result left by an earlier test in this session.
    svc.SP500HeatmapService._cache.clear()
    svc.SP500HeatmapService._cache_times.clear()
    return written


# ─────────────────────────────────────────────────────────────────────────────
# Background-activity tracking
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class WorkerError:
    label: str
    fn: str
    error: str


class ActivityTracker:
    """Tracks background threads and CalculationWorker failures.

    ``label`` is attached to every recorded event; set it to the module id
    being exercised so failures are attributed to a module.
    """

    def __init__(self) -> None:
        self.label = "startup"
        self._qthreads: List[weakref.ref] = []
        self._pythreads: List[threading.Thread] = []
        self._lock = threading.Lock()
        self.starts = 0
        self.worker_errors: List[WorkerError] = []
        self.worker_runs: List[Tuple[str, str]] = []

    # -- installation ---------------------------------------------------

    def install(self, monkeypatch) -> "ActivityTracker":
        from PySide6.QtCore import QThread

        from app.services.calculation_worker import CalculationWorker

        tracker = self
        real_qstart = QThread.start
        real_tstart = threading.Thread.start
        real_run = CalculationWorker.run

        def tracking_qstart(thread, *args, **kwargs):
            with tracker._lock:
                tracker._qthreads.append(weakref.ref(thread))
                tracker.starts += 1
            return real_qstart(thread, *args, **kwargs)

        def tracking_tstart(thread, *args, **kwargs):
            with tracker._lock:
                tracker._pythreads.append(thread)
                tracker.starts += 1
            return real_tstart(thread, *args, **kwargs)

        def recording_run(worker):
            label = tracker.label
            fn = getattr(worker, "_fn", None)
            name = getattr(fn, "__qualname__", None) or repr(fn)
            try:
                return real_run(worker)
            finally:
                tracker.worker_runs.append((label, name))
                if worker.error_msg is not None:
                    tracker.worker_errors.append(WorkerError(label, name, str(worker.error_msg)))

        monkeypatch.setattr(QThread, "start", tracking_qstart)
        monkeypatch.setattr(threading.Thread, "start", tracking_tstart)
        monkeypatch.setattr(CalculationWorker, "run", recording_run)
        return self

    # -- queries --------------------------------------------------------

    def running(self) -> List[str]:
        """Descriptions of tracked threads that are still running."""
        alive = []
        with self._lock:
            qrefs = list(self._qthreads)
            pythreads = list(self._pythreads)
        for ref in qrefs:
            thread = ref()
            if thread is None:
                continue
            try:
                if thread.isRunning():
                    alive.append(f"QThread {type(thread).__name__}")
            except RuntimeError:  # C++ object already deleted
                continue
        for thread in pythreads:
            if thread.is_alive():
                alive.append(f"Thread {thread.name}")
        return alive

    def _prune(self) -> None:
        with self._lock:
            kept = []
            for ref in self._qthreads:
                thread = ref()
                if thread is None:
                    continue
                try:
                    if thread.isRunning():
                        kept.append(ref)
                except RuntimeError:
                    continue
            self._qthreads = kept
            self._pythreads = [t for t in self._pythreads if t.is_alive()]

    def wait_idle(self, qapp, widget=None, *, timeout: float = 60.0, settle_ms: int = 150,
                  poll_ms: int = 20) -> Tuple[bool, float, List[str]]:
        """Process events until no tracked thread runs and ``widget`` has no worker.

        The idle state must hold for ``settle_ms`` with no new thread started
        (so chained loads and queued completion callbacks are included).
        Returns ``(idle, seconds_waited, still_busy_descriptions)``.
        """
        from PySide6.QtTest import QTest

        t0 = time.monotonic()
        deadline = t0 + timeout
        idle_since: Optional[float] = None
        starts_seen = self.starts
        while True:
            QTest.qWait(poll_ms)
            busy = self.running()
            if widget is not None:
                busy += _widget_busy(widget)
            now = time.monotonic()
            if busy or self.starts != starts_seen:
                idle_since = None
                starts_seen = self.starts
            elif idle_since is None:
                idle_since = now
            elif (now - idle_since) * 1000.0 >= settle_ms:
                self._prune()
                return True, now - t0, []
            if now >= deadline:
                return False, now - t0, busy


def _widget_busy(widget) -> List[str]:
    """Worker slots on a module that are still occupied (BaseModule convention)."""
    busy = []
    try:
        if getattr(widget, "_worker", None) is not None:
            busy.append(f"{type(widget).__name__}._worker")
    except RuntimeError:
        pass
    return busy


# ─────────────────────────────────────────────────────────────────────────────
# Error capture
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Event:
    label: str
    kind: str
    text: str

    def short(self, limit: int = 600) -> str:
        text = self.text if len(self.text) <= limit else self.text[:limit] + " ..."
        return f"[{self.label}] {self.kind}: {text}"


class _ListHandler(logging.Handler):
    def __init__(self, capture: "ErrorCapture"):
        super().__init__(level=logging.WARNING)
        self.capture = capture

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - broken format args
            msg = str(record.msg)
        if record.exc_info:
            msg += "\n" + "".join(traceback.format_exception(*record.exc_info))
        kind = f"log.{record.levelname}"
        self.capture.add(kind, f"{record.name}: {msg}", levelno=record.levelno)


class ErrorCapture:
    """Collects exceptions, Qt messages and WARNING+ log records, labelled by module."""

    def __init__(self, tracker: Optional[ActivityTracker] = None) -> None:
        self.tracker = tracker
        self.events: List[Event] = []
        self.warnings: List[Event] = []
        self._lock = threading.Lock()
        self._handler = _ListHandler(self)
        self._prev_qt_handler = None
        self._installed_qt = False

    @property
    def label(self) -> str:
        return self.tracker.label if self.tracker is not None else "?"

    def add(self, kind: str, text: str, *, levelno: int = logging.ERROR) -> None:
        event = Event(self.label, kind, text)
        with self._lock:
            (self.events if levelno >= logging.ERROR else self.warnings).append(event)

    def install(self, monkeypatch) -> "ErrorCapture":
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler

        def excepthook(exc_type, exc, tb):
            self.add("uncaught", "".join(traceback.format_exception(exc_type, exc, tb)))

        def thread_excepthook(args):
            self.add(
                f"thread-uncaught[{getattr(args.thread, 'name', '?')}]",
                "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
            )

        def unraisablehook(unraisable):
            exc = unraisable.exc_value
            text = "".join(traceback.format_exception(type(exc), exc, unraisable.exc_traceback)) if exc else ""
            self.add("unraisable", f"{unraisable.err_msg or ''} {unraisable.object!r}\n{text}")

        monkeypatch.setattr(sys, "excepthook", excepthook)
        monkeypatch.setattr(threading, "excepthook", thread_excepthook)
        monkeypatch.setattr(sys, "unraisablehook", unraisablehook)

        root = logging.getLogger()
        root.addHandler(self._handler)
        self._prev_root_level = root.level
        if root.level > logging.WARNING or root.level == logging.NOTSET:
            root.setLevel(logging.WARNING)

        def qt_handler(msg_type, context, message):
            text = str(message)
            if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                self.add(f"qt.{msg_type.name}", text)
            elif msg_type == QtMsgType.QtWarningMsg:
                if any(fragment in text for fragment in QT_WARNING_ERRORS):
                    self.add("qt.QtWarningMsg(thread/lifetime)", text)
                else:
                    self.add("qt.QtWarningMsg", text, levelno=logging.WARNING)

        self._prev_qt_handler = qInstallMessageHandler(qt_handler)
        self._installed_qt = True
        return self

    def uninstall(self) -> None:
        from PySide6.QtCore import qInstallMessageHandler

        root = logging.getLogger()
        root.removeHandler(self._handler)
        root.setLevel(self._prev_root_level)
        if self._installed_qt:
            qInstallMessageHandler(self._prev_qt_handler)
            self._installed_qt = False

    def scan_output(self, text: str) -> None:
        """Record every printed traceback found in captured stdout/stderr ``text``."""
        if TRACEBACK_MARKER not in text:
            return
        chunks = text.split(TRACEBACK_MARKER)
        for chunk in chunks[1:]:
            lines = [ln for ln in chunk.splitlines() if ln.strip()]
            tail = "\n".join(lines[-6:])
            self.add("printed-traceback", TRACEBACK_MARKER + "\n...\n" + tail)


# ─────────────────────────────────────────────────────────────────────────────
# Module state
# ─────────────────────────────────────────────────────────────────────────────


def module_state(widget) -> Dict[str, Any]:
    """Small, generic description of a module after its initial load."""
    from app.ui.modules.fred_base_module import FredDataModule

    state: Dict[str, Any] = {"class": type(widget).__name__, "fred_like": isinstance(widget, FredDataModule)}
    if state["fred_like"]:
        state["data_loaded"] = widget._data is not None
        state["placeholder"] = _placeholder_text(getattr(widget, "chart", None))
    return state


def _placeholder_text(chart) -> Optional[str]:
    if chart is None:
        return None
    label = getattr(chart, "_placeholder", None)
    try:
        if label is not None and hasattr(label, "isVisible") and label.isVisible():
            return label.text()
    except RuntimeError:
        return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Frozen clock (visual captures)
# ─────────────────────────────────────────────────────────────────────────────


class FrozenClock:
    """Freeze calendar "now" for app code: datetime, pandas and Qt.

    * ``datetime.datetime`` / ``datetime.date`` are replaced (in the
      ``datetime`` module and in every loaded module that bound them by name)
      by subclasses whose ``now/today/utcnow`` return :attr:`now`;
      ``isinstance`` checks against them still accept real instances.
    * ``pandas.Timestamp.now/today`` and ``QDate.currentDate`` /
      ``QDateTime.currentDateTime`` are patched too.

    ``time.time()`` is NOT frozen (it only drives cache ages and cooldowns).
    Call :meth:`uninstall` (the visual fixture does) to undo everything,
    including bindings made by modules first imported while frozen.
    """

    def __init__(self, now: _dt.datetime = FROZEN_NOW, tz_name: str = FROZEN_TZ) -> None:
        from zoneinfo import ZoneInfo

        self.now = now
        self.aware = now.replace(tzinfo=ZoneInfo(tz_name))
        self._real_dt = _dt.datetime
        self._real_date = _dt.date
        self._patches: List[Tuple[Any, str, Any]] = []
        self.frozen_datetime, self.frozen_date = self._make_classes()

    def _make_classes(self):
        real_dt, real_date = self._real_dt, self._real_date
        naive, aware = self.now, self.aware

        class _DateMeta(type):
            def __instancecheck__(cls, obj):
                return isinstance(obj, real_date)

            def __subclasscheck__(cls, sub):
                return issubclass(sub, real_date)

        class _DatetimeMeta(type):
            def __instancecheck__(cls, obj):
                return isinstance(obj, real_dt)

            def __subclasscheck__(cls, sub):
                return issubclass(sub, real_dt)

        class FrozenDate(real_date, metaclass=_DateMeta):
            @classmethod
            def today(cls):
                return real_date(naive.year, naive.month, naive.day)

        class FrozenDatetime(real_dt, metaclass=_DatetimeMeta):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return real_dt(naive.year, naive.month, naive.day, naive.hour, naive.minute, naive.second)
                return aware.astimezone(tz)

            @classmethod
            def today(cls):
                return cls.now()

            @classmethod
            def utcnow(cls):
                return aware.astimezone(_dt.timezone.utc).replace(tzinfo=None)

        FrozenDate.__name__ = FrozenDate.__qualname__ = "date"
        FrozenDatetime.__name__ = FrozenDatetime.__qualname__ = "datetime"
        return FrozenDatetime, FrozenDate

    def _set(self, owner, attr, value) -> None:
        self._patches.append((owner, attr, getattr(owner, attr)))
        setattr(owner, attr, value)

    def install(self) -> "FrozenClock":
        import pandas as pd
        from PySide6.QtCore import QDate, QDateTime, QTime

        frozen_dt, frozen_date = self.frozen_datetime, self.frozen_date
        self._set(_dt, "datetime", frozen_dt)
        self._set(_dt, "date", frozen_date)
        for mod_name, mod in list(sys.modules.items()):
            if mod is None or not (mod_name == "app" or mod_name.startswith("app.")):
                continue
            for attr, value in list(vars(mod).items()):
                if value is self._real_dt:
                    self._set(mod, attr, frozen_dt)
                elif value is self._real_date:
                    self._set(mod, attr, frozen_date)

        naive, aware = self.now, self.aware

        def ts_now(cls, tz=None):
            if tz is None:
                return pd.Timestamp(naive)
            return pd.Timestamp(aware).tz_convert(tz)

        def ts_today(cls, tz=None):
            return ts_now(cls, tz)

        self._set(pd.Timestamp, "now", classmethod(ts_now))
        self._set(pd.Timestamp, "today", classmethod(ts_today))
        qdate = QDate(naive.year, naive.month, naive.day)
        qdatetime = QDateTime(qdate, QTime(naive.hour, naive.minute, naive.second))
        self._set(QDate, "currentDate", staticmethod(lambda: QDate(qdate)))
        self._set(QDateTime, "currentDateTime", staticmethod(lambda: QDateTime(qdatetime)))
        return self

    def uninstall(self) -> None:
        for owner, attr, old in reversed(self._patches):
            setattr(owner, attr, old)
        self._patches.clear()
        # Modules first imported while frozen bound the frozen classes: rebind.
        for mod in list(sys.modules.values()):
            if mod is None:
                continue
            try:
                items = list(vars(mod).items())
            except TypeError:
                continue
            for attr, value in items:
                if value is self.frozen_datetime:
                    setattr(mod, attr, self._real_dt)
                elif value is self.frozen_date:
                    setattr(mod, attr, self._real_date)


def seed_randomness(seed: int = 12345) -> None:
    """Reset the global RNGs (numpy + random) before a deterministic capture."""
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed)


def format_events(events: List[Event], limit: int = 40) -> str:
    lines = [e.short() for e in events[:limit]]
    if len(events) > limit:
        lines.append(f"... and {len(events) - limit} more")
    return "\n".join(lines)
