"""Characterization: the settings contract of every registered module.  [P0.T3]

Static part (default run, no widgets) - for every entry in
``app.core.config.MODULE_SECTIONS`` the settings manager the module would
create (via the real ``BaseModule._create_settings_manager`` on a proxy), its
settings file name, ``DEFAULT_SETTINGS`` (keys and values),
``get_settings_options()`` (checkbox dialog keys + labels) and the dialog title
are goldened in ``tests/goldens/settings/<module_id>.static.json``.

Live part (``--full``) - each module is built offscreen in its own empty home
(``fresh_home``, workers stubbed) and its settings button is clicked through
the real ``settings_clicked`` signal.  The dialog that opens (checkbox or
custom) is captured without blocking, "saved" the way its Save button would
and its ``get_settings()`` keys and values are goldened in
``<module_id>.live.json``, together with the keys that do not round-trip
(default settings, then every boolean setting flipped).  The dialog always
returns "Rejected" so the module itself never applies anything.

Saved settings must survive the refactor (user decision 1), so any change to
these goldens belongs in a ``Behavior-Change: yes`` commit with a migration.
"""

from __future__ import annotations

import enum
import importlib
import inspect
import sys

import pytest

from app.core.config import MODULE_SECTIONS
from golden_utils import assert_golden, canonicalize

AREA = "settings"

ALL_ENTRIES = [entry for entries in MODULE_SECTIONS.values() for entry in entries]
ALL_IDS = [entry["id"] for entry in ALL_ENTRIES]
MACRO_IDS = [entry["id"] for entry in MODULE_SECTIONS["Macro"]]

# Modules without any persisted settings (asserted, so the list stays honest).
NO_SETTINGS = {"import_data", "settings"}
# Modules that do not derive from BaseModule create their manager by hand.
_NON_BASEMODULE_MANAGERS = {"PortfolioConstructionModule": "PortfolioSettingsManager"}
# Macro modules without a lookback control.
NO_LOOKBACK = {"rate_probability"}

FIXED_RISK_FREE = 0.0425  # what the performance-metrics dialog shows for ^IRX


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _module_class(module_id: str):
    for entry in ALL_ENTRIES:
        if entry["id"] == module_id:
            mod_name, cls_name = entry["class"].split(":")
            return getattr(importlib.import_module(mod_name), cls_name)
    raise KeyError(module_id)


class _Proxy:
    """Stands in for a module instance without building a QWidget.

    Instance attributes win; anything else is looked up on ``cls`` and plain
    functions are bound to the proxy, so ``cls.method(proxy)`` runs the real
    method body.
    """

    def __init__(self, cls, **attrs):
        self.__dict__["_cls"] = cls
        self.__dict__.update(attrs)

    def __getattr__(self, name):
        cls = self.__dict__["_cls"]
        raw = inspect.getattr_static(cls, name)
        if isinstance(raw, staticmethod):
            return raw.__func__
        if isinstance(raw, classmethod):
            return raw.__func__.__get__(cls)
        if inspect.isfunction(raw):
            return raw.__get__(self)
        return getattr(cls, name)


def _plain(value):
    """JSON-able form: enums -> 'Type.Name', tuples -> lists (recursively)."""
    if isinstance(value, enum.Enum):
        return f"{type(value).__name__}.{value.name}"
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return canonicalize(value)


def _static_manager(cls):
    """The settings manager ``cls`` creates, built without instantiating ``cls``."""
    from app.ui.modules.base_module import BaseModule

    if issubclass(cls, BaseModule):
        return BaseModule._create_settings_manager(_Proxy(cls))
    manager_name = _NON_BASEMODULE_MANAGERS.get(cls.__name__)
    if manager_name is None:
        return None
    return getattr(sys.modules[cls.__module__], manager_name)()


def _static_snapshot(cls) -> dict:
    mgr = _static_manager(cls)
    proxy = _Proxy(cls)
    has_options = hasattr(cls, "get_settings_options")
    return {
        "settings_file": mgr.settings_filename if mgr is not None else None,
        "defaults": _plain(mgr.DEFAULT_SETTINGS) if mgr is not None else None,
        "options": [[k, label] for k, label in proxy.get_settings_options()] if has_options else None,
        "dialog_title": proxy.get_settings_dialog_title() if has_options else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Static snapshot (no widgets)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.golden
@pytest.mark.parametrize("module_id", ALL_IDS)
def test_settings_static_snapshot(module_id, fresh_home):
    cls = _module_class(module_id)
    snap = _static_snapshot(cls)

    assert (snap["settings_file"] is None) == (module_id in NO_SETTINGS), module_id
    if snap["defaults"] is not None:
        assert snap["settings_file"].endswith(".json")
        assert all(isinstance(k, str) for k in snap["defaults"])
        # a fresh home has no saved file, so the manager starts on its defaults
        assert _plain(_static_manager(cls).get_all_settings()) == snap["defaults"]
    option_keys = [k for k, _ in snap["options"] or []]
    assert len(option_keys) == len(set(option_keys)), f"{module_id}: duplicate option keys"
    assert set(option_keys) <= set(snap["defaults"] or {}), (
        f"{module_id}: checkbox options without a default: {sorted(set(option_keys) - set(snap['defaults'] or {}))}"
    )

    assert_golden(f"{module_id}.static", snap, area=AREA)


# Lookbacks that are lost on reload because the defaults have no "lookback" key
# (BaseSettingsManager.load_settings keeps only keys present in the defaults).
_LOOKBACK_NOT_PERSISTED = {
    "yields": pytest.mark.xfail(strict=True, reason="KNOWN-BUG:treasury-lookback-persist"),
    "cpi": pytest.mark.xfail(strict=True, reason="KNOWN-BUG:cpi-lookback-persist"),
}


@pytest.mark.parametrize(
    "module_id",
    [pytest.param(i, marks=_LOOKBACK_NOT_PERSISTED.get(i, ())) for i in MACRO_IDS if i not in NO_LOOKBACK],
)
def test_lookback_setting_survives_reload(module_id, fresh_home):
    """``update_settings({'lookback': ...})`` then a new manager reads it back."""
    cls = _module_class(module_id)
    _static_manager(cls).update_settings({"lookback": "2020-01-15"})
    assert _static_manager(cls).get_setting("lookback") == "2020-01-15"


@pytest.mark.xfail(strict=True, reason="KNOWN-BUG:chart-settings-persist")
def test_chart_display_settings_survive_reload(fresh_home):
    """The chart settings dialog saves show_gridlines / show_crosshair /
    show_mouse_price_label, but they are not in ChartSettingsManager's
    defaults, so ``load_settings`` drops them on the next start."""
    cls = _module_class("charts")
    saved = {"show_gridlines": True, "show_crosshair": False, "show_mouse_price_label": False}
    _static_manager(cls).update_settings(saved)
    reloaded = _static_manager(cls)
    assert {k: reloaded.get_setting(k) for k in saved} == saved


# ─────────────────────────────────────────────────────────────────────────────
# Live snapshot (offscreen widgets)
# ─────────────────────────────────────────────────────────────────────────────


def _no_worker(self, fn, *args, **kwargs):
    """Stand-in for ``BaseModule._run_worker`` (no threads, no fetches)."""
    return None


@pytest.fixture
def make_module(qapp, theme_manager, fresh_home, monkeypatch):
    """Build registry modules offscreen in an isolated home, without workers."""
    from PySide6.QtCore import QCoreApplication, QEvent

    from app.services.statistics_service import StatisticsService
    from app.ui.modules.base_module import BaseModule

    monkeypatch.setattr(BaseModule, "_run_worker", _no_worker)
    monkeypatch.setattr(StatisticsService, "get_risk_free_rate", staticmethod(lambda: FIXED_RISK_FREE))
    created = []

    def make(module_id: str):
        widget = _module_class(module_id)(theme_manager)
        created.append(widget)
        return widget

    yield make
    for widget in created:
        widget.hide()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _live_manager(module):
    return getattr(module, "settings_manager", None) or getattr(module, "_settings_manager", None)


def _settings_emitter(module):
    for name in ("toolbar", "controls"):
        bar = getattr(module, name, None)
        if bar is not None and hasattr(bar, "settings_clicked"):
            return bar
    return None


def _open_settings_dialog(module, recorder):
    """Click the settings button; return the captured dialog's settings.

    Returns ``(dialog_class_name, values)`` or ``None`` when no dialog with
    ``get_settings`` opened.  Dialogs that only fill ``result`` on Save get
    their ``_save_settings`` (the Save button slot) called first.
    """
    captured = []

    def on_exec(dialog):
        if hasattr(dialog, "get_settings") and not captured:
            values = dialog.get_settings()
            if not isinstance(values, dict) and hasattr(dialog, "_save_settings"):
                dialog._save_settings()
                values = dialog.get_settings()
            captured.append((type(dialog).__name__, values))
        return 0  # Rejected: the module applies nothing

    recorder.on_exec = on_exec
    try:
        _settings_emitter(module).settings_clicked.emit()
    finally:
        recorder.on_exec = None
    return captured[0] if captured else None


def _not_roundtripped(values: dict, current: dict) -> list:
    return sorted(k for k in values if k in current and _plain(values[k]) != _plain(current[k]))


@pytest.mark.ui
@pytest.mark.golden
@pytest.mark.parametrize("module_id", ALL_IDS)
def test_settings_live_snapshot(module_id, make_module, nonblocking_dialogs, fresh_home):
    cls = _module_class(module_id)
    static = _static_snapshot(cls)
    module = make_module(module_id)
    mgr = _live_manager(module)

    # the instance agrees with the static snapshot
    assert (mgr is None) == (static["settings_file"] is None), module_id
    if mgr is not None:
        assert mgr.settings_filename == static["settings_file"]
        assert _plain(mgr.DEFAULT_SETTINGS) == static["defaults"]
    if static["options"] is not None:
        assert [[k, label] for k, label in module.get_settings_options()] == static["options"]

    snap = {
        "settings_button": _settings_emitter(module) is not None,
        "settings_file_written_on_init": (
            (fresh_home / ".quant_terminal" / static["settings_file"]).exists() if mgr is not None else None
        ),
        "changed_on_init": (
            {k: v for k, v in _plain(mgr.get_all_settings()).items() if static["defaults"].get(k) != v}
            if mgr is not None
            else None
        ),
        "dialog": None,
    }

    if module_id in NO_SETTINGS:
        assert mgr is None and not nonblocking_dialogs.calls
    else:
        assert snap["settings_button"], f"{module_id}: no toolbar/controls with settings_clicked"
        current = mgr.get_all_settings()
        opened = _open_settings_dialog(module, nonblocking_dialogs)
        assert opened is not None, f"{module_id}: the settings button opened no settings dialog"
        _dialog_cls, values = opened
        assert isinstance(values, dict), f"{module_id}: get_settings() -> {values!r}"
        if static["options"]:
            assert set(values) == {k for k, _ in static["options"]}, module_id

        # second pass: every boolean setting flipped before opening the dialog
        flipped = {k: not v for k, v in current.items() if isinstance(v, bool)}
        mgr.update_settings(flipped)
        flipped_current = mgr.get_all_settings()
        _cls2, flipped_values = _open_settings_dialog(module, nonblocking_dialogs)
        assert isinstance(flipped_values, dict) and set(flipped_values) == set(values), module_id

        snap["dialog"] = {
            "keys": sorted(values),
            "values": _plain(values),
            "keys_not_in_defaults": sorted(set(values) - set(static["defaults"])),
            "not_roundtripped": _not_roundtripped(values, current),
            "flipped_not_roundtripped": _not_roundtripped(flipped_values, flipped_current),
        }

    assert_golden(f"{module_id}.live", snap, area=AREA)


@pytest.mark.ui
@pytest.mark.xfail(strict=True, reason="KNOWN-BUG:volatility-threshold-strip")
def test_volatility_dialog_keeps_thresholds(make_module, nonblocking_dialogs):
    """ValidatedNumericLineEdit(decimals=0).setValue(20) strips the trailing
    zero of the integer ("20" -> "2"), so opening and saving the Volatility
    settings turns the 20/30 VIX thresholds into 2/3."""
    module = make_module("volatility")
    assert module.settings_manager.get_setting("threshold_1") == 20
    _cls, values = _open_settings_dialog(module, nonblocking_dialogs)
    assert (values["threshold_1"], values["threshold_2"]) == (20, 30)
