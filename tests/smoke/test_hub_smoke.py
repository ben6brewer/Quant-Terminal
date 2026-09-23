"""Hub smoke test: build the hub like ``app.main.main()``, open EVERY registered
module, cycle the 3 themes and resize, with FakeFred/FakeYahoo and the network
guard active.

One hub session (~2-3 min) runs lazily inside the first test that needs it
(with that test's ``fresh_home``/fakes/network guard active) and records
everything per module; the tests below then assert on the recorded result:

* ``test_hub_startup_and_global`` - ``main()`` contract (registration, default
  ``has_own_home_button=True``, starts on the home screen, never enters the
  real event loop) and problems not attributable to one module (startup,
  theme switches on the home screen, home-screen resizes).
* ``test_module_smoke[<id>]`` - one verdict per registered module.  A module
  fails on: not instantiable/openable, background work not finished within
  the bounded wait, uncaught exceptions (main thread, Python threads,
  unraisable), Qt critical/fatal messages or thread-affinity warnings, ERROR
  log records, printed tracebacks, ``CalculationWorker`` errors, message
  boxes, a FRED/yfinance module that ends without data, still "theme dirty"
  after being shown in a new theme, or a container that does not fill the
  window after a resize.

Known product bugs are strict xfails (``KNOWN_BUGS``); the fixing phase deletes
the entry.

Run:  pytest --full tests/smoke/test_hub_smoke.py
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pytest

from smoke.hub_harness import (
    THEMES,
    ActivityTracker,
    ErrorCapture,
    Event,
    build_hub_like_main,
    close_hub,
    ensure_fonts,
    module_state,
    registered_entries,
    registered_module_ids,
    seed_offline_caches,
)

MODULE_LOAD_TIMEOUT_S = 60.0  # per module, initial load (bounded wait)
RESHOW_TIMEOUT_S = 20.0  # per module, re-show after a theme change
RESIZE_SIZES = ((1024, 640), (1600, 900), (1280, 800))
SESSION_TIMEOUT_S = 600  # the first test to run carries the whole session (~2-3 min)
GLOBAL = "<hub>"

# module id -> KNOWN-BUG id (strict xfail; remove the entry when fixed)
KNOWN_BUGS: Dict[str, str] = {
    # money_velocity_chart.py: strftime("Q%q %Y") raises ValueError on
    # pandas 3 -> uncaught exception in _on_data_fetched on every render.
    "money_velocity": "KNOWN-BUG:money-velocity-qfmt",
}


# ─────────────────────────────────────────────────────────────────────────────
# One recorded hub session
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SessionResult:
    ids: List[str]
    fatal: Optional[str] = None
    main_checks: List[str] = field(default_factory=list)  # failed main() contract checks
    problems: Dict[str, List[str]] = field(default_factory=dict)  # module id or GLOBAL -> problems
    states: Dict[str, dict] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    worker_runs: int = 0

    def add(self, key: str, problem: str) -> None:
        self.problems.setdefault(key, []).append(problem)


_SESSION: Dict[str, SessionResult] = {}


def _owner(label: str, ids: set) -> str:
    """Map an event label ("gdp", "gdp@dark", "gdp@resize", "theme:dark") to a module id."""
    base = label.split("@", 1)[0]
    return base if base in ids else GLOBAL


def _run_hub_session(qapp, monkeypatch, nonblocking_dialogs, capfd) -> SessionResult:
    ids = registered_module_ids()
    result = SessionResult(ids=ids)
    idset = set(ids)
    t_start = time.monotonic()
    tracker = ActivityTracker().install(monkeypatch)
    capture = ErrorCapture(tracker).install(monkeypatch)
    dialog_seen = 0
    hub = run = None

    def checkpoint() -> None:
        """Attribute captured output and new dialog calls to the current label."""
        nonlocal dialog_seen
        out, err = capfd.readouterr()
        capture.scan_output(out + err)
        calls = nonblocking_dialogs.calls[dialog_seen:]
        dialog_seen = len(nonblocking_dialogs.calls)
        for kind, detail in calls:
            if kind.startswith("QMessageBox.") or (kind == "exec" and "MessageBox" in detail):
                capture.add("message-box", f"{kind} {detail}")

    try:
        assert ensure_fonts(), "no fonts available to the offscreen platform"
        seed_offline_caches()

        # ── Build exactly like app.main.main() ───────────────────────────
        run = build_hub_like_main(monkeypatch)
        hub, theme_manager = run.hub, run.theme_manager
        checks = {
            "main() returned 0 from the (shimmed) event loop": run.return_code == 0,
            "main() entered the event loop exactly once": run.exec_calls == 1,
            "main() showed the hub": hub.isVisible(),
            "hub starts on the home screen": hub.main_stack.currentWidget() is hub.home_screen,
            "fresh home -> default theme 'bloomberg'": theme_manager.current_theme == "bloomberg",
            "no duplicate module ids": len(ids) == len(idset),
            "main() registered every configured module": set(hub._module_factories) == idset,
        }
        for entry in registered_entries():
            opts = hub._module_options.get(entry["id"])
            checks[f"{entry['id']}: has_own_home_button defaults to True in main()"] = opts == {
                "has_own_home_button": entry.get("has_own_home_button", True)
            }
        result.main_checks = [name for name, ok in checks.items() if not ok]
        tracker.label = "startup"
        tracker.wait_idle(qapp, timeout=10.0)
        checkpoint()

        def guarded(step, *args) -> None:
            """Run one per-module step; an exception escaping it is recorded, not fatal."""
            try:
                step(*args)
            except Exception as exc:  # e.g. a Python override of showEvent raising
                capture.add("escaped-exception", "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)))
            checkpoint()

        # ── Phase 1: open every module and wait for its initial load ─────
        def open_initial(mid):
            hub.open_module(mid)
            widget = hub.modules.get(mid)
            if widget is None:
                result.add(mid, "could not be instantiated/opened (hub.open_module swallowed the error)")
                return
            result.states[mid] = {"class": type(widget).__name__, "fred_like": False}
            if hub.main_stack.currentWidget() is not hub.module_containers[mid]:
                result.add(mid, "not the current page after hub.open_module")
            idle, waited, busy = tracker.wait_idle(qapp, widget, timeout=MODULE_LOAD_TIMEOUT_S)
            result.timings[mid] = round(waited, 2)
            if not idle:
                result.add(mid, f"initial load still busy after {waited:.0f}s: {busy}")
            state = module_state(widget)
            result.states[mid] = state
            if state["fred_like"] and not state["data_loaded"]:
                result.add(mid, f"ended without data; placeholder={state.get('placeholder')!r}")

        for mid in ids:
            tracker.label = mid
            guarded(open_initial, mid)

        # ── Phase 2: cycle the 3 themes; re-show every module in each ────
        def reshow(mid, theme):
            widget = hub.modules[mid]
            hub.open_module(mid)
            hub.grab()  # force a full paint of the visible module
            idle, waited, busy = tracker.wait_idle(qapp, widget, timeout=RESHOW_TIMEOUT_S, settle_ms=50)
            if not idle:
                result.add(mid, f"@{theme}: still busy after {waited:.0f}s: {busy}")
            if getattr(widget, "_theme_dirty", False):
                result.add(mid, f"@{theme}: still theme-dirty after being shown")

        def switch_theme(theme):
            hub.show_home()
            theme_manager.set_theme(theme)
            tracker.wait_idle(qapp, timeout=RESHOW_TIMEOUT_S)
            if theme_manager.current_theme != theme:
                result.add(GLOBAL, f"set_theme({theme!r}) did not stick")

        for theme in THEMES:
            tracker.label = f"theme:{theme}"
            guarded(switch_theme, theme)
            for mid in ids:
                if mid in hub.modules:
                    tracker.label = f"{mid}@{theme}"
                    guarded(reshow, mid, theme)

        # ── Phase 3: resize the window with every module visible ─────────
        # The window cannot shrink below its layout minimum, so the expected
        # size is the request expanded to hub.minimumSize().
        from PySide6.QtCore import QSize

        def resize_module(mid):
            hub.open_module(mid)
            container = hub.module_containers[mid]
            for w, h in RESIZE_SIZES:
                hub.resize(w, h)
                qapp.processEvents()
                expected = QSize(w, h).expandedTo(hub.minimumSize()).boundedTo(hub.maximumSize())
                if hub.size() != expected:
                    result.add(mid, f"resize {w}x{h}: expected {expected.width()}x{expected.height()}, "
                                    f"got {hub.width()}x{hub.height()}")
                if container.size() != hub.main_stack.size():
                    result.add(mid, f"resize {w}x{h}: container {container.width()}x{container.height()} "
                                    f"does not fill the stack {hub.main_stack.width()}x{hub.main_stack.height()}")
            hub.grab()

        def resize_home():
            hub.show_home()
            for w, h in RESIZE_SIZES:
                hub.resize(w, h)
                qapp.processEvents()
            hub.grab()
            tracker.wait_idle(qapp, timeout=RESHOW_TIMEOUT_S)

        for mid in ids:
            if mid in hub.modules:
                tracker.label = f"{mid}@resize"
                guarded(resize_module, mid)
        tracker.label = "home@resize"
        guarded(resize_home)
    except Exception as exc:  # recorded; every test reports it
        result.fatal = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    finally:
        capture.uninstall()
        if hub is not None:
            tracker.label = "teardown"
            close_hub(hub, qapp, run)

    for event in capture.events:
        result.add(_owner(event.label, idset), _event_text(event))
    for err in tracker.worker_errors:
        result.add(_owner(err.label, idset), f"CalculationWorker error in {err.fn}: {err.error}")
    result.warnings = [e.short(300) for e in capture.warnings]
    result.worker_runs = len(tracker.worker_runs)
    result.elapsed_s = round(time.monotonic() - t_start, 1)
    return result


def _event_text(event: Event) -> str:
    text = event.text.strip()
    if len(text) > 1500:  # keep the head (where) and the tail (the exception)
        text = text[:300] + "\n  ...\n" + text[-1200:]
    return f"{event.label}: {event.kind}: {text}"


@pytest.fixture
def hub_session(qapp, monkeypatch, fresh_home, fake_fred, fake_yahoo, nonblocking_dialogs, capfd):
    """The recorded hub session (runs once per test session, in the first test that asks)."""
    if "result" not in _SESSION:
        _SESSION["result"] = _run_hub_session(qapp, monkeypatch, nonblocking_dialogs, capfd)
    result = _SESSION["result"]
    assert result.fatal is None, f"hub session aborted:\n{result.fatal}"
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.ui
@pytest.mark.timeout(SESSION_TIMEOUT_S)
def test_hub_startup_and_global(hub_session):
    r = hub_session
    slowest = sorted(r.timings.items(), key=lambda kv: -kv[1])[:5]
    print(f"\nhub smoke: {len(r.ids)} modules in {r.elapsed_s}s, {r.worker_runs} worker runs, "
          f"{len(r.warnings)} Qt/log warnings; slowest initial loads: {slowest}")
    for w in r.warnings:
        print("  warning:", w)
    assert not r.main_checks, f"main() contract broken: {r.main_checks}"
    problems = r.problems.get(GLOBAL, [])
    assert not problems, "hub-level problems:\n" + "\n\n".join(problems)


def _module_params():
    params = []
    for mid in registered_module_ids():
        marks = []
        if mid in KNOWN_BUGS:
            marks.append(pytest.mark.xfail(strict=True, reason=KNOWN_BUGS[mid]))
        params.append(pytest.param(mid, marks=marks, id=mid))
    return params


@pytest.mark.ui
@pytest.mark.timeout(SESSION_TIMEOUT_S)
@pytest.mark.parametrize("module_id", _module_params())
def test_module_smoke(hub_session, module_id):
    r = hub_session
    assert module_id in r.states, f"{module_id} was never opened: {r.problems.get(module_id)}"
    problems = r.problems.get(module_id, [])
    assert not problems, f"{module_id}:\n" + "\n\n".join(problems)


def test_known_bug_ids_are_registered():
    """Every KNOWN_BUGS key must still be a registered module id (stale entries hide nothing)."""
    stale = sorted(set(KNOWN_BUGS) - set(registered_module_ids()))
    assert not stale, f"KNOWN_BUGS entries for unregistered modules: {stale}"
