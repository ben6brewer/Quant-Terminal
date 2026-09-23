"""Visual capture: every registered module x 3 themes at 1600x900, frozen clock.

Not collected unless ``--visual``::

    QT_VISUAL_LABEL=base pytest --visual tests/visual
    python tests/visual/compare.py base <other-label>

Output (always OUTSIDE the repo): ``$QT_VISUAL_OUT``, else
``<visual root>/<$QT_VISUAL_LABEL or "latest">`` (see ``compare.capture_dir``),
laid out as ``<theme>/<module_id>.png`` (plus ``<theme>/_home.png``) and a
``manifest.json`` with per-module load state and any errors seen.

Determinism: FakeFred/FakeYahoo data, a fresh home, the clock frozen at
2026-06-30 22:00 (the fakes' last day, after the US close), global RNGs
re-seeded before every first open, a fixed set of system fonts with a pinned
default font (Segoe UI 9pt, as on Windows) and family substitutions, no cursor
blinking, and a bounded wait for every module's background work followed by
a settle period.  Two captures of the same code must compare IDENTICAL.

The test fails only when a capture is missing, has the wrong size or is
blank; product errors are recorded in the manifest (the smoke test in
``tests/smoke`` is the place that fails on them).
"""

from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pytest

from smoke.hub_harness import (
    APP_FONT,
    FROZEN_NOW,
    THEMES,
    ActivityTracker,
    ErrorCapture,
    FrozenClock,
    build_hub_like_main,
    close_hub,
    ensure_fonts,
    module_state,
    pin_app_font,
    registered_module_ids,
    seed_offline_caches,
    seed_randomness,
)
from visual.compare import capture_dir

pytestmark = pytest.mark.visual

WIDTH, HEIGHT = 1600, 900
# bloomberg first: it is the startup theme, so first opens happen in it.
CAPTURE_THEMES = ("bloomberg",) + tuple(t for t in THEMES if t != "bloomberg")
LOAD_TIMEOUT_S = 60.0
SETTLE_MS = 400  # after idle: lets 50-100 ms single-shot label/positioning timers run
HOME_ID = "_home"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _prepare_out_dir() -> Path:
    out = capture_dir().resolve()
    try:
        out.relative_to(REPO_ROOT)
    except ValueError:
        pass
    else:
        pytest.fail(f"visual output must be outside the repo, got {out}")
    out.mkdir(parents=True, exist_ok=True)
    # Remove only files this harness writes (stale modules would show up as
    # "only in A/B" in compare.py).
    for theme in CAPTURE_THEMES:
        for png in (out / theme).glob("*.png"):
            png.unlink()
    (out / "manifest.json").unlink(missing_ok=True)
    return out


def _distinct_colors(image) -> int:
    """Number of distinct colours on a 1-in-7 pixel grid (blank pages have 1-2)."""
    import numpy as np

    img = image.convertToFormat(image.Format.Format_RGBA8888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    arr = np.frombuffer(img.constBits(), dtype=np.uint8, count=h * bpl).reshape(h, bpl)[:, : w * 4]
    sample = np.ascontiguousarray(arr.reshape(h, w, 4)[::7, ::7]).reshape(-1, 4)
    return len(np.unique(sample.view(np.uint32)))


def _grab(hub, qapp, path: Path) -> dict:
    from PySide6.QtTest import QTest

    QTest.qWait(SETTLE_MS)
    qapp.processEvents()
    image = hub.grab().toImage()
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = image.save(str(path))
    return {"saved": ok, "size": [image.width(), image.height()], "colors": _distinct_colors(image)}


@pytest.mark.timeout(1200)  # ~4 min on the dev machine
def test_capture_every_module_in_every_theme(qapp, monkeypatch, fresh_home, fake_fred, fake_yahoo,
                                             nonblocking_dialogs, capfd):
    from PySide6.QtGui import QGuiApplication

    out = _prepare_out_dir()
    ids = registered_module_ids()
    fonts = ensure_fonts()
    assert fonts, "no fonts available to the offscreen platform"
    hints = QGuiApplication.styleHints()
    old_flash = hints.cursorFlashTime()
    hints.setCursorFlashTime(0)  # no blinking text cursor
    unpin_font = pin_app_font()
    clock = FrozenClock().install()
    tracker = ActivityTracker().install(monkeypatch)
    capture = ErrorCapture(tracker).install(monkeypatch)
    hub = run = None
    manifest = {
        "label": out.name,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frozen_now": FROZEN_NOW.isoformat(),
        "size": [WIDTH, HEIGHT],
        "themes": list(CAPTURE_THEMES),
        "fonts": fonts,
        "app_font": list(APP_FONT),
        "modules": {},
    }
    shots = {}
    t0 = time.monotonic()
    try:
        seed_offline_caches()
        run = build_hub_like_main(monkeypatch)
        hub, theme_manager = run.hub, run.theme_manager
        hub.setGeometry(0, 0, WIDTH, HEIGHT)
        assert theme_manager.current_theme == CAPTURE_THEMES[0]
        def shoot(mid, theme):
            first_open = mid not in hub.modules
            if first_open:
                seed_randomness()
            hub.open_module(mid)
            widget = hub.modules.get(mid)
            entry = manifest["modules"].setdefault(mid, {"errors": []})
            if widget is None:
                entry["errors"].append(f"{theme}: could not be opened")
                return
            idle, waited, busy = tracker.wait_idle(qapp, widget, timeout=LOAD_TIMEOUT_S)
            if first_open:
                entry.update(module_state(widget))
                entry["load_s"] = round(waited, 2)
            if not idle:
                entry["errors"].append(f"{theme}: still busy after {waited:.0f}s: {busy}")
            hub.setGeometry(0, 0, WIDTH, HEIGHT)
            shots[(mid, theme)] = _grab(hub, qapp, out / theme / f"{mid}.png")

        for theme in CAPTURE_THEMES:
            tracker.label = f"theme:{theme}"
            hub.show_home()
            theme_manager.set_theme(theme)
            tracker.wait_idle(qapp, timeout=LOAD_TIMEOUT_S)
            hub.setGeometry(0, 0, WIDTH, HEIGHT)
            shots[(HOME_ID, theme)] = _grab(hub, qapp, out / theme / f"{HOME_ID}.png")
            for mid in ids:
                tracker.label = f"{mid}@{theme}"
                try:
                    shoot(mid, theme)
                except Exception as exc:  # keep capturing the other modules
                    capture.add("escaped-exception", "".join(
                        traceback.format_exception(type(exc), exc, exc.__traceback__)))
                capfd.readouterr()
    finally:
        capture.uninstall()
        clock.uninstall()
        hints.setCursorFlashTime(old_flash)
        unpin_font()
        if hub is not None:
            close_hub(hub, qapp, run)
        for event in capture.events:
            mid = event.label.split("@", 1)[0]
            target = manifest["modules"].get(mid)
            text = event.short(400)
            if target is not None:
                target["errors"].append(text)
            else:
                manifest.setdefault("hub_errors", []).append(text)
        for err in tracker.worker_errors:
            mid = err.label.split("@", 1)[0]
            manifest["modules"].setdefault(mid, {"errors": []})["errors"].append(
                f"CalculationWorker error in {err.fn}: {err.error}")
        manifest["elapsed_s"] = round(time.monotonic() - t0, 1)
        manifest["shots"] = {f"{t}/{m}": s for (m, t), s in sorted(shots.items())}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print(f"\nvisual capture: {len(shots)} PNGs in {out} ({manifest['elapsed_s']}s)")
    expected = {(m, t) for t in CAPTURE_THEMES for m in [HOME_ID] + ids}
    missing = sorted(expected - set(shots))
    assert not missing, f"not captured: {missing}"
    bad = {f"{t}/{m}": s for (m, t), s in shots.items()
           if not s["saved"] or s["size"] != [WIDTH, HEIGHT] or s["colors"] < 3}
    assert not bad, f"unsaved, wrongly sized or blank captures: {bad}"
    for m, t in expected:
        assert (out / t / f"{m}.png").is_file()
