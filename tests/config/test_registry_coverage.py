"""Registry coverage: every entry in ``app.core.config.MODULE_SECTIONS`` resolves to a
widget class. Every home-screen tile also has a ``MODULE_INFO`` entry and a
tile screenshot. The reverse holds too: no info entry and no screenshot
exists without a module.

What the checks mirror in the app:

* Tiles: ``ModuleTileGrid`` builds one tile per entry of every section
  whose name does not start with ``_``. That is ``config.ALL_MODULES``.
  The ``_Settings`` section is internal and has no tile.
* Info: ``BaseModule`` looks up ``get_module_info(type(self).__name__)``,
  so the key is the resolved class's ``__name__``.
* Screenshot: ``ScreenshotManager.get_screenshot_path(module_id)``, i.e.
  ``app/assets/screenshots/<id>.png``. A missing file falls back to
  ``coming_soon.png``.

Current gaps are strict xfails with KNOWN-BUG ids. Fixing a gap turns the
xfail into an XPASS failure, so the marker has to be removed.
"""

from __future__ import annotations

import importlib

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from app.core.config import ALL_MODULES, MODULE_SECTIONS
from app.ui.modules.module_info import MODULE_INFO
from app.utils.screenshot_manager import ScreenshotManager

# Internal (non-tile) registry entries. They are importable but need no
# tile, no screenshot and no info panel.
INTERNAL_IDS = {"settings"}

MISSING_MODULE_INFO = {
    "import_data": "KNOWN-BUG:module-info-missing ImportDataModule has no MODULE_INFO entry",
}
MISSING_SCREENSHOT = {
    "import_data": "KNOWN-BUG:tile-screenshot-missing import_data tile shows coming_soon.png",
    "unemployment_age": "KNOWN-BUG:tile-screenshot-missing unemployment_age tile shows coming_soon.png",
}
# Tile screenshots stored as JPEG under a .png name (Qt sniffs the content,
# so they render). P2 B-startup re-encodes every screenshot as a real PNG.
JPEG_NAMED_PNG = {
    "crude_oil",
    "durable_goods",
    "financial_conditions",
    "gdp",
    "government_debt",
    "mortgage_rates",
    "personal_income",
    "retail_sales",
    "savings_rate",
    "trade_balance",
}

PLACEHOLDER = "coming_soon"
REQUIRED_INFO_KEYS = {"title", "description", "calculation", "data_sources", "source"}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

ALL_ENTRIES = [entry for entries in MODULE_SECTIONS.values() for entry in entries]
TILE_ENTRIES = list(ALL_MODULES)
TILE_IDS = {entry["id"] for entry in TILE_ENTRIES}
SCREENSHOT_DIR = ScreenshotManager.get_screenshot_path(PLACEHOLDER).parent


def _resolve(entry) -> type:
    module_path, class_name = entry["class"].split(":")
    return getattr(importlib.import_module(module_path), class_name)


def _params(entries, xfails: dict):
    return [
        pytest.param(
            entry,
            id=entry["id"],
            marks=[pytest.mark.xfail(strict=True, raises=AssertionError, reason=xfails[entry["id"]])]
            if entry["id"] in xfails
            else [],
        )
        for entry in entries
    ]


# ── registry shape ──────────────────────────────────────────────────────────


def test_internal_entries_are_exactly_the_underscore_sections():
    internal = {e["id"] for name, es in MODULE_SECTIONS.items() if name.startswith("_") for e in es}
    assert internal == INTERNAL_IDS
    assert TILE_IDS.isdisjoint(INTERNAL_IDS)
    assert len(TILE_ENTRIES) + len(INTERNAL_IDS) == len(ALL_ENTRIES)


def test_known_gap_lists_name_registered_tiles():
    """Stale-entry guard: every known gap must still name a registered tile."""
    for gap_list in (MISSING_MODULE_INFO, MISSING_SCREENSHOT, JPEG_NAMED_PNG):
        assert set(gap_list) <= TILE_IDS, sorted(set(gap_list) - TILE_IDS)


@pytest.mark.parametrize("entry", ALL_ENTRIES, ids=lambda e: e["id"])
def test_entry_resolves_to_widget_class(entry):
    cls = _resolve(entry)
    class_name = entry["class"].split(":")[1]
    assert isinstance(cls, type) and issubclass(cls, QWidget)
    # the info lookup key is type(self).__name__, so the registry name must match it
    assert cls.__name__ == class_name
    assert isinstance(entry["label"], str) and entry["label"].strip()
    assert isinstance(entry.get("has_own_home_button", True), bool)


# ── module info ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("entry", _params(TILE_ENTRIES, MISSING_MODULE_INFO))
def test_tile_has_module_info(entry):
    cls = _resolve(entry)
    info = MODULE_INFO.get(cls.__name__)
    assert info is not None, f"no MODULE_INFO entry for {cls.__name__} (tile {entry['id']!r})"
    assert REQUIRED_INFO_KEYS <= set(info), sorted(REQUIRED_INFO_KEYS - set(info))
    for key in ("title", "description", "calculation", "source"):
        assert isinstance(info[key], str) and info[key].strip(), f"{cls.__name__}.{key} is empty"
    assert isinstance(info["data_sources"], list) and info["data_sources"]
    for source in info["data_sources"]:
        assert set(source) == {"id", "name", "frequency"}, source


def test_every_module_info_entry_belongs_to_a_registered_class():
    registered_classes = {entry["class"].split(":")[1] for entry in ALL_ENTRIES}
    assert sorted(set(MODULE_INFO) - registered_classes) == []


# ── tile screenshots ────────────────────────────────────────────────────────


@pytest.mark.parametrize("entry", _params(TILE_ENTRIES, MISSING_SCREENSHOT))
def test_tile_has_screenshot(entry, qapp):
    module_id = entry["id"]
    assert ScreenshotManager.has_screenshot(module_id), f"no tile screenshot for {module_id!r}"
    image = QImage(str(ScreenshotManager.get_screenshot_path(module_id)))
    assert not image.isNull(), f"{module_id}.png does not decode"
    assert image.width() >= 453 and image.height() >= 255


def test_placeholder_screenshot_exists(qapp):
    path = ScreenshotManager.get_screenshot_path(PLACEHOLDER)
    assert path.is_file()
    assert not QImage(str(path)).isNull()


def test_every_screenshot_belongs_to_a_tile():
    stems = {p.stem for p in SCREENSHOT_DIR.glob("*.png")}
    assert len(stems) > 50  # sanity: we are looking at the real asset dir
    assert sorted(stems - TILE_IDS - {PLACEHOLDER}) == []
    non_png_names = sorted(p.name for p in SCREENSHOT_DIR.iterdir() if p.is_file() and p.suffix != ".png")
    assert non_png_names == []


@pytest.mark.parametrize(
    "stem",
    [
        pytest.param(
            p.stem,
            marks=[
                pytest.mark.xfail(
                    strict=True,
                    raises=AssertionError,
                    reason="KNOWN-BUG:screenshot-jpeg-as-png JPEG data under a .png name; P2 re-encodes",
                )
            ]
            if p.stem in JPEG_NAMED_PNG
            else [],
        )
        for p in sorted(SCREENSHOT_DIR.glob("*.png"))
    ],
)
def test_screenshot_is_real_png(stem):
    header = (SCREENSHOT_DIR / f"{stem}.png").read_bytes()[: len(PNG_MAGIC)]
    assert header == PNG_MAGIC, f"{stem}.png is not PNG data (starts with {header[:4]!r})"
