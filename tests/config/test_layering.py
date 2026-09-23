"""Import layering: ``app.services`` and ``app.core`` must not import ``app.ui``.

The check is a static AST scan, so function-local (lazy) imports,
``TYPE_CHECKING`` blocks, relative imports and literal
``importlib.import_module("app.ui...")`` / ``__import__`` calls all count.

``ALLOWED_UI_IMPORTS`` lists the violations that exist today, and the
scan must match it EXACTLY:

* a new violation fails the test;
* removing a violation also fails the test until its entry is removed
  from the allowlist.

So the allowlist can only shrink, and it must be empty at FINAL.
Entries are (file relative to src/, imported module); line numbers are
left out on purpose.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import app

SRC_DIR = Path(app.__file__).resolve().parent.parent
LOWER_LAYERS = ("app/services", "app/core")
UI_PACKAGE = "app.ui"

# Current violations. P7 M-portfolio moves PortfolioPersistence and the
# PortfolioService core into app/services/portfolio/, which removes both.
ALLOWED_UI_IMPORTS = {
    (
        "app/services/portfolio_data_service.py",
        "app.ui.modules.portfolio_construction.services.portfolio_persistence",
    ),
    (
        "app/services/portfolio_data_service.py",
        "app.ui.modules.portfolio_construction.services.portfolio_service",
    ),
}


def _is_ui(name: str) -> bool:
    return name == UI_PACKAGE or name.startswith(UI_PACKAGE + ".")


def _resolve_relative(module_name: str, is_package: bool, level: int, target: str | None) -> str:
    """Absolute module named by ``from <'.' * level><target> import ...`` inside ``module_name``."""
    parts = module_name.split(".")
    base = parts if is_package else parts[:-1]
    if level - 1 > len(base):
        raise ValueError(f"relative import beyond top-level package in {module_name}")
    base = base[: len(base) - (level - 1)]
    return ".".join(base + ([target] if target else []))


def ui_imports_in_source(source: str, module_name: str, is_package: bool = False) -> set[str]:
    """Return every ``app.ui[...]`` module that ``source`` imports (statically)."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names if _is_ui(alias.name))
        elif isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative(module_name, is_package, node.level, node.module)
                if node.level
                else (node.module or "")
            )
            if _is_ui(base):
                found.add(base)
            else:  # `from app import ui` / `from .. import ui`
                found.update(f"{base}.{a.name}" for a in node.names if _is_ui(f"{base}.{a.name}"))
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in {"import_module", "__import__"} and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _is_ui(arg.value):
                    found.add(arg.value)
    return found


def _module_name(path: Path) -> tuple[str, bool]:
    parts = list(path.relative_to(SRC_DIR).with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts), is_package


def scan_lower_layers() -> set[tuple[str, str]]:
    violations = set()
    for layer in LOWER_LAYERS:
        for path in sorted((SRC_DIR / layer).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            module_name, is_package = _module_name(path)
            source = path.read_text(encoding="utf-8")
            for imported in ui_imports_in_source(source, module_name, is_package):
                violations.add((path.relative_to(SRC_DIR).as_posix(), imported))
    return violations


def test_lower_layers_exist():
    """Sanity: the scan looks at the real packages, not an empty directory."""
    for layer in LOWER_LAYERS:
        assert (SRC_DIR / layer / "__init__.py").is_file(), f"{layer} is not a package under {SRC_DIR}"
    assert len(list((SRC_DIR / "app/services").rglob("*.py"))) >= 20
    assert (SRC_DIR / "app/core/config.py").is_file()


def test_services_and_core_do_not_import_ui_beyond_allowlist():
    violations = scan_lower_layers()
    new = sorted(violations - ALLOWED_UI_IMPORTS)
    fixed = sorted(ALLOWED_UI_IMPORTS - violations)
    assert not new, f"NEW app.services/app.core -> app.ui imports (move the code down a layer instead): {new}"
    assert not fixed, f"these allowlisted violations are gone; delete them from ALLOWED_UI_IMPORTS: {fixed}"


# ── self-tests for the scanner, so a green result means something ──────────

_SCANNER_CASES = [
    pytest.param("import app.ui.hub_window", "app.services.x", False, {"app.ui.hub_window"}, id="import"),
    pytest.param("import app.ui", "app.services.x", False, {"app.ui"}, id="import-package"),
    pytest.param("from app.ui.modules import gdp", "app.services.x", False, {"app.ui.modules"}, id="from-absolute"),
    pytest.param("from app import ui", "app.core.x", False, {"app.ui"}, id="from-app-import-ui"),
    pytest.param("from ..ui.widgets import common", "app.services.x", False, {"app.ui.widgets"}, id="relative-2"),
    pytest.param("from .. import ui", "app.core.config", False, {"app.ui"}, id="relative-import-ui"),
    pytest.param("from ...ui import hub_window", "app.services.fred", True, {"app.ui"}, id="relative-from-package"),
    pytest.param(
        "def f():\n    from app.ui.modules.module_info import MODULE_INFO\n",
        "app.services.x",
        False,
        {"app.ui.modules.module_info"},
        id="function-local",
    ),
    pytest.param(
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.ui.hub_window import HubWindow\n",
        "app.core.x",
        False,
        {"app.ui.hub_window"},
        id="type-checking",
    ),
    pytest.param(
        "import importlib\nm = importlib.import_module('app.ui.modules.gdp')\n",
        "app.services.x",
        False,
        {"app.ui.modules.gdp"},
        id="import_module-literal",
    ),
    pytest.param("__import__('app.ui.hub_window')", "app.services.x", False, {"app.ui.hub_window"}, id="dunder-import"),
    pytest.param("from app.utils import formatters\nimport app.core.config", "app.services.x", False, set(), id="clean"),
    pytest.param("import app.uix", "app.services.x", False, set(), id="prefix-lookalike"),
    pytest.param("from . import ui_helpers", "app.services.x", False, set(), id="relative-sibling"),
    pytest.param('CLASS = "app.ui.modules.gdp:GdpModule"', "app.core.config", False, set(), id="plain-string"),
]


@pytest.mark.parametrize("source, module_name, is_package, expected", _SCANNER_CASES)
def test_scanner_detects_ui_imports(source, module_name, is_package, expected):
    assert ui_imports_in_source(source, module_name, is_package) == expected
