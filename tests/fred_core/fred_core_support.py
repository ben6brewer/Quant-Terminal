"""Shared helpers for the FRED data-layer characterization tests (P0.T1).

* :func:`discover_fred_service_classes` imports every module under
  ``app.ui.modules.<pkg>.services`` (plus ``app.services.fred`` once P4 moves
  the services there) and returns every concrete ``BaseFredService``
  subclass defined in ``app``.
* :func:`service_snapshot` turns a ``fetch_all_data()`` result into the
  canonical golden structure (``frame_digest`` per output key plus
  ``get_latest_stats``).
* :func:`reset_fetch_cooldowns` clears the class-level cooldown timestamps
  (``_last_*_fetch``) so earlier tests cannot short-circuit a fetch.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from golden_utils import frame_digest

GOLDEN_AREA = "fred_core"

# Output frames whose COLUMN ORDER today depends on thread completion order:
# ``_fetch_full`` builds the group frame from a dict filled inside
# ``as_completed(...)``, and these outputs hand that raw frame (or a
# transform of it) straight through.  Their goldens use sorted columns;
# every other output keeps its real (deterministic) column order.
# ``test_completion_order_allowlist_is_complete`` proves this list is a
# superset of the keys whose order actually varies.
COMPLETION_ORDER_KEYS = frozenset({
    ("InflationFredService", "cpi"),
    ("InflationFredService", "pce"),
    ("InflationFredService", "ppi"),
    ("InflationFredService", "expectations"),
    ("LaborMarketFredService", "claims"),
    ("TreasuryFredService", "treasury"),
})

_COOLDOWN_ATTR = re.compile(r"^_last_\w*fetch\w*$")


def _import_quietly(name: str, errors: Dict[str, str]) -> None:
    try:
        importlib.import_module(name)
    except Exception as exc:  # reported by test_discovery_imports_cleanly
        errors[name] = f"{type(exc).__name__}: {exc}"


def import_fred_service_modules() -> Dict[str, str]:
    """Import every ``app.ui.modules.*.services`` module (and ``app.services.fred``).

    Returns ``{module_name: error}`` for modules that failed to import.
    """
    import app.ui.modules as modules_pkg

    errors: Dict[str, str] = {}
    for base in modules_pkg.__path__:
        for info in sorted(pkgutil.iter_modules([base]), key=lambda i: i.name):
            svc_dir = Path(base) / info.name / "services"
            if not info.ispkg or not (svc_dir / "__init__.py").is_file():
                continue
            pkg_name = f"app.ui.modules.{info.name}.services"
            _import_quietly(pkg_name, errors)
            for sub in sorted(pkgutil.walk_packages([str(svc_dir)], pkg_name + "."),
                              key=lambda i: i.name):
                _import_quietly(sub.name, errors)

    # P4 moves the services to app/services/fred/**; walk it when present.
    fred_dir = Path(importlib.import_module("app.services").__path__[0]) / "fred"
    if (fred_dir / "__init__.py").is_file():
        _import_quietly("app.services.fred", errors)
        for sub in sorted(pkgutil.walk_packages([str(fred_dir)], "app.services.fred."),
                          key=lambda i: i.name):
            _import_quietly(sub.name, errors)
    return errors


def _all_subclasses(root: type) -> List[type]:
    out, stack, seen = [], list(root.__subclasses__()), set()
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        out.append(cls)
        stack.extend(cls.__subclasses__())
    return out


def discover_fred_service_classes() -> Tuple[List[type], Dict[str, str]]:
    """``(classes sorted by name, import errors)`` for every concrete FRED service.

    Concrete = declares ``GROUPS`` or overrides ``fetch_all_data``.  Only
    classes defined in ``app.*`` count (test-local probe subclasses are ignored).
    """
    errors = import_fred_service_modules()
    from app.services.base_fred_service import BaseFredService

    found = []
    for cls in _all_subclasses(BaseFredService):
        if not (cls.__module__ or "").startswith("app."):
            continue
        overrides_fetch = cls.fetch_all_data.__func__ is not BaseFredService.fetch_all_data.__func__
        if cls.GROUPS or overrides_fetch:
            found.append(cls)
    found.sort(key=lambda c: (c.__name__, c.__module__))
    return found, errors


def reset_fetch_cooldowns(monkeypatch, cls: type) -> None:
    """Null every ``_last_*fetch*`` cooldown timestamp on ``cls`` (restored after the test)."""
    names = {n for n in dir(cls) if _COOLDOWN_ATTR.match(n)}
    names.update(f"_last_group_{i}_fetch" for i in range(len(getattr(cls, "GROUPS", []) or [])))
    for name in sorted(names):
        monkeypatch.setattr(cls, name, None, raising=False)
    if hasattr(cls, "_data"):
        monkeypatch.setattr(cls, "_data", None, raising=False)


def output_digest(service_name: str, key: str, obj) -> dict:
    """``frame_digest`` of one output; completion-order keys get sorted columns."""
    if isinstance(obj, pd.DataFrame) and (service_name, key) in COMPLETION_ORDER_KEYS:
        obj = obj[sorted(obj.columns)]
    return frame_digest(obj)


def service_snapshot(cls: type, result, fred_ids) -> dict:
    """Golden payload for ``cls.fetch_all_data()`` -> ``result``."""
    name = cls.__name__
    stats_fn = getattr(cls, "get_latest_stats", None)
    return {
        "service": name,
        "outputs": {k: output_digest(name, k, v) for k, v in result.items()},
        "has_get_latest_stats": stats_fn is not None,
        "latest_stats": stats_fn(result) if stats_fn is not None else None,
        "fred_ids": sorted(set(fred_ids)),
    }
