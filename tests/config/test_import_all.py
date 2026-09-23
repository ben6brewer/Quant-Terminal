"""Import every ``app.*`` module.

One fresh child interpreter (see ``conftest.run_child``) walks the
package with ``pkgutil.walk_packages``, the same discovery that
PyInstaller's ``collect_submodules("app")`` hook relies on, and imports
every module it finds. Each module then gets its own test here.

* Every ``.py`` file under ``src/app`` must be discoverable by the walk. A
  directory without ``__init__.py`` silently drops out of the frozen build.
* Every module must import. ``KNOWN_IMPORT_FAILURES`` lists today's
  exceptions as strict xfails with KNOWN-BUG ids. Each one must still fail
  with the recorded error: a different error is a real failure, and a
  successful import is an XPASS, so the entry must then be removed.
* Custom indicator plugins are loaded the way
  ``IndicatorService.load_custom_indicator_plugins`` loads them: by file
  path, with the plugin directory on ``sys.path``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

import app

APP_DIR = Path(app.__file__).resolve().parent
SRC_DIR = APP_DIR.parent
PLUGIN_DIR = APP_DIR / "ui" / "modules" / "chart" / "custom_indicators"


@dataclass(frozen=True)
class KnownFailure:
    bug_id: str
    error: str  # substring of "<ExceptionType>: <message>"
    why: str


KNOWN_IMPORT_FAILURES = {
    "app.ui.widgets.create_indicator_dialog": KnownFailure(
        "KNOWN-BUG:dead-create-indicator-dialog",
        "ModuleNotFoundError: No module named 'app.ui.widgets.custom_message_box'",
        "dead duplicate of chart/widgets/create_indicator_dialog.py with stale imports; P1 D-shell deletes it",
    ),
    "app.ui.modules.chart.custom_indicators.death_golden_cross": KnownFailure(
        "KNOWN-BUG:plugin-toplevel-import",
        "ModuleNotFoundError: No module named 'base_indicator'",
        "plugin uses a top-level `from base_indicator import ...`, so it only loads through "
        "IndicatorService's sys.path insert and not as an app.* submodule "
        "(collect_submodules warns on it)",
    ),
}


def _module_names_on_disk() -> list[str]:
    names = set()
    for path in APP_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        parts = list(path.relative_to(SRC_DIR).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        names.add(".".join(parts))
    return sorted(names)


ALL_MODULE_NAMES = _module_names_on_disk()
PLUGIN_FILES = sorted(
    p.name for p in PLUGIN_DIR.glob("*.py") if not p.name.startswith("__") and p.name != "base_indicator.py"
)

_IMPORT_ALL_CHILD = """
import importlib
import importlib.util
import pkgutil
import traceback

import app

walk_errors = {}


def _on_walk_error(name):
    exc = sys.exc_info()[1]
    walk_errors[name] = f"{type(exc).__name__}: {exc}"


walked = [info.name for info in pkgutil.walk_packages(app.__path__, "app.", onerror=_on_walk_error)]

imported, failed, tracebacks = [], {}, {}
for name in walked:
    try:
        importlib.import_module(name)
    except BaseException as exc:  # noqa: BLE001 - record SystemExit/KeyboardInterrupt too
        failed[name] = f"{type(exc).__name__}: {exc}"
        tracebacks[name] = traceback.format_exc()[-3000:]
    else:
        imported.append(name)

# Plugins: mirror IndicatorService.load_custom_indicator_plugins
plugin_dir = SRC_DIR / "app" / "ui" / "modules" / "chart" / "custom_indicators"
sys.path.insert(0, str(plugin_dir))
plugins = {}
for plugin_file in sorted(plugin_dir.glob("*.py")):
    if plugin_file.name.startswith("__") or plugin_file.name == "base_indicator.py":
        continue
    try:
        spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[plugin_file.stem] = module
        spec.loader.exec_module(module)
        classes = sorted(
            attr_name
            for attr_name in dir(module)
            if isinstance(getattr(module, attr_name), type)
            and hasattr(getattr(module, attr_name), "calculate")
            and hasattr(getattr(module, attr_name), "NAME")
            and attr_name != "BaseIndicator"
        )
        plugins[plugin_file.name] = {"classes": classes, "error": None}
    except BaseException as exc:  # noqa: BLE001
        plugins[plugin_file.name] = {"classes": [], "error": f"{type(exc).__name__}: {exc}"}

write_result({
    "app_location": app_location(),
    "walked": walked,
    "walk_errors": walk_errors,
    "imported": imported,
    "failed": failed,
    "tracebacks": tracebacks,
    "plugins": plugins,
})
"""


@pytest.fixture(scope="module")
def import_all(run_child):
    return run_child("import_all", _IMPORT_ALL_CHILD)


def test_discovered_every_module_on_disk(import_all):
    assert len(ALL_MODULE_NAMES) > 300  # sanity: scanning the real tree
    assert import_all["walk_errors"] == {}
    walked = set(import_all["walked"]) | {"app"}  # walk_packages yields submodules only
    assert sorted(set(ALL_MODULE_NAMES) - walked) == [], "modules invisible to walk_packages (missing __init__.py?)"
    assert sorted(walked - set(ALL_MODULE_NAMES)) == []


def test_known_failures_are_real_modules():
    """Stale-entry guard: every allowlisted module still exists on disk."""
    assert sorted(set(KNOWN_IMPORT_FAILURES) - set(ALL_MODULE_NAMES)) == []


def _module_params():
    params = []
    for name in ALL_MODULE_NAMES:
        if name == "app":
            continue
        known = KNOWN_IMPORT_FAILURES.get(name)
        marks = (
            [pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{known.bug_id} {known.why}")]
            if known
            else []
        )
        params.append(pytest.param(name, id=name, marks=marks))
    return params


@pytest.mark.parametrize("module_name", _module_params())
def test_module_imports(import_all, module_name):
    error = import_all["failed"].get(module_name)
    known = KNOWN_IMPORT_FAILURES.get(module_name)
    if known is not None and error is not None and known.error not in error:
        pytest.fail(f"{module_name} ({known.bug_id}) now fails differently: {error}", pytrace=False)
    assert error is None, f"import {module_name} failed: {error}\n{import_all['tracebacks'].get(module_name, '')}"
    assert module_name in import_all["imported"]


@pytest.mark.parametrize("plugin_file", PLUGIN_FILES)
def test_custom_indicator_plugin_loads_like_indicator_service(import_all, plugin_file):
    result = import_all["plugins"][plugin_file]
    assert result["error"] is None, f"plugin {plugin_file} failed to load: {result['error']}"
    assert len(result["classes"]) >= 1, f"plugin {plugin_file} defines no indicator class (NAME + calculate)"


def test_plugin_files_found():
    assert PLUGIN_FILES, f"no custom indicator plugins under {PLUGIN_DIR}"
