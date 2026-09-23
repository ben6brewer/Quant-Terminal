"""Orphan packages: every directory under ``src/app/ui/modules`` is a
registered module package or is explicitly allowlisted.

A registered package is the first component after ``app.ui.modules.`` of
some registry class path in ``app.core.config.MODULE_SECTIONS``.

The allowlists record today's unregistered packages:

* ``SERVICE_ONLY_PACKAGES``: the FRED "hub" packages. They hold only a
  ``services/`` subpackage that other modules import. P4 moves them to
  ``app/services/fred/`` behind shims, and P5.3 deletes them.
* ``DEAD_UI_PACKAGES``: complete UI modules that nothing registers
  (dead code). P1 D-fred deletes them.

The allowlists must stay exact. A stale entry (the directory is gone, or
it is now registered) fails the test, so they only shrink. Both must be
empty at FINAL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app
from app.core.config import MODULE_SECTIONS

MODULES_DIR = Path(app.__file__).resolve().parent / "ui" / "modules"
MODULES_PREFIX = "app.ui.modules."

SERVICE_ONLY_PACKAGES = {
    "banking",
    "commodities",
    "consumer",
    "credit",
    "currency",
    "financial_conditions",
    "fiscal",
    "home_market",
    "household",
    "housing",
    "income",
    "inflation",
    "ism",
    "labor_market",
    "manufacturing",
    "monetary_policy",
    "mortgage",
    "productivity_service",
    "recession",
    "retail",
    "stress",
    "trade",
    "volatility_index",
    "wealth_inequality",
}

DEAD_UI_PACKAGES = {
    "ism_manufacturing",
    "ism_services",
    "recession_indicators",
}

ALLOWLIST = SERVICE_ONLY_PACKAGES | DEAD_UI_PACKAGES


def _registered_packages() -> set[str]:
    pkgs = set()
    for entries in MODULE_SECTIONS.values():
        for entry in entries:
            module_path = entry["class"].split(":")[0]
            if module_path.startswith(MODULES_PREFIX):
                pkgs.add(module_path[len(MODULES_PREFIX):].split(".")[0])
    return pkgs


def _module_dirs() -> set[str]:
    return {p.name for p in MODULES_DIR.iterdir() if p.is_dir() and p.name != "__pycache__"}


REGISTERED = _registered_packages()
MODULE_DIRS = _module_dirs()


def test_modules_dir_is_populated():
    assert len(MODULE_DIRS) >= 50
    # module files (settings_module.py) count as registered but are not dirs
    assert {"chart", "analysis", "gdp", "treasury"} <= MODULE_DIRS & REGISTERED


def test_allowlists_are_disjoint():
    assert SERVICE_ONLY_PACKAGES.isdisjoint(DEAD_UI_PACKAGES)


def test_every_module_dir_is_registered_or_allowlisted():
    orphans = sorted(MODULE_DIRS - REGISTERED - ALLOWLIST)
    assert not orphans, (
        f"unregistered packages under app/ui/modules: {orphans}. Register them in "
        "app.core.config or delete them. Do not grow the allowlist."
    )


def test_allowlist_has_no_stale_entries():
    missing = sorted(ALLOWLIST - MODULE_DIRS)
    now_registered = sorted(ALLOWLIST & REGISTERED)
    assert not missing, f"allowlisted packages no longer exist; remove them from the allowlist: {missing}"
    assert not now_registered, f"allowlisted packages are now registered; remove them from the allowlist: {now_registered}"


def test_every_registered_package_exists():
    for pkg in sorted(REGISTERED):
        as_dir = MODULES_DIR / pkg / "__init__.py"
        as_file = MODULES_DIR / f"{pkg}.py"
        assert as_dir.is_file() or as_file.is_file(), f"registry points at missing package app.ui.modules.{pkg}"


@pytest.mark.parametrize("pkg", sorted(SERVICE_ONLY_PACKAGES))
def test_service_only_package_has_no_ui(pkg):
    """A service-only package holds services, not a hidden, unregistered module UI."""
    root = MODULES_DIR / pkg
    assert (root / "services" / "__init__.py").is_file(), f"{pkg}: expected a services/ subpackage"
    ui_files = sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
        and (p.name.endswith("_module.py") or "widgets" in p.relative_to(root).parts)
    )
    assert ui_files == [], f"{pkg} is allowlisted as service-only but contains UI code: {ui_files}"


@pytest.mark.parametrize("pkg", sorted(DEAD_UI_PACKAGES))
def test_dead_ui_package_is_a_full_module(pkg):
    """Dead UI packages are whole modules (not stray service code)."""
    root = MODULES_DIR / pkg
    assert sorted(p.name for p in root.glob("*_module.py")) == [f"{pkg}_module.py"]
    assert (root / "widgets" / "__init__.py").is_file()
