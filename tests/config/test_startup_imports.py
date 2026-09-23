"""Startup import guard: what a fresh interpreter loads to build the hub.

``app.ui.hub_window`` is what ``app.main`` needs before the first paint.
Anything heavy that it pulls in costs startup time on every launch.

Today ``app/__init__.py`` imports ``app._compat`` (a pandas shim for the
unused ``pandas_datareader``), and ``app/utils/__init__.py`` re-exports
helpers, so pandas, numpy and pyarrow load at startup. P2 (B-startup)
deletes ``_compat`` and empties ``utils/__init__``. When that lands, the
strict xfail below turns into an XPASS failure, and whoever lands the fix
must remove the marker.
"""

from __future__ import annotations

import pytest

from app.core.config import MODULE_SECTIONS

# Libraries that the hub_window import does NOT pull in today. This is a
# regression guard: none of them may start loading at startup.
HEAVY_LIBS_NOT_LOADED_TODAY = (
    "fredapi",
    "matplotlib",
    "pyqtgraph",
    "requests",
    "scipy",
    "sklearn",
    "statsmodels",
    "yfinance",
)

_STARTUP_CHILD = """
import app.ui.hub_window  # the import under test, first thing after the prelude

loaded = sorted(sys.modules)
write_result({
    "app_location": app_location(),
    "top_level": sorted({name.split(".")[0] for name in loaded}),
    "app_modules": [name for name in loaded if name == "app" or name.startswith("app.")],
    "has_hub_window": hasattr(sys.modules["app.ui.hub_window"], "HubWindow"),
})
"""


@pytest.fixture(scope="module")
def startup_modules(run_child):
    return run_child("startup_hub_window", _STARTUP_CHILD)


def test_hub_window_imports_in_fresh_interpreter(startup_modules):
    assert startup_modules["has_hub_window"] is True
    assert "app.ui.hub_window" in startup_modules["app_modules"]


def test_registered_modules_stay_lazy(startup_modules):
    """The hub shell must not import any registered feature module.

    main.py imports each registry class on first open. An eager import from
    the hub would load every module (and its data stack) at startup.
    """
    registered = {entry["class"].split(":")[0] for entries in MODULE_SECTIONS.values() for entry in entries}
    assert len(registered) > 50  # sanity: the registry was read
    eager = sorted(registered & set(startup_modules["app_modules"]))
    assert eager == []


@pytest.mark.parametrize("lib", HEAVY_LIBS_NOT_LOADED_TODAY)
def test_hub_window_import_does_not_load_heavy_lib(startup_modules, lib):
    assert lib not in startup_modules["top_level"], f"{lib} is now imported at startup via app.ui.hub_window"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="KNOWN-BUG:startup-pandas app/__init__ -> _compat (and utils/__init__) import pandas at startup; fixed in P2 B-startup",
)
def test_hub_window_import_does_not_load_pandas(startup_modules):
    assert "pandas" not in startup_modules["top_level"], "pandas is imported at startup via app.ui.hub_window"
