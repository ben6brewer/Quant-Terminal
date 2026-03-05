"""Tests that every registered module class is importable."""

import importlib

import pytest

from app.core.config import ALL_MODULES, MODULE_SECTIONS


def _all_module_entries():
    """Collect all module entries including internal sections."""
    entries = []
    for section_name, modules in MODULE_SECTIONS.items():
        for mod in modules:
            entries.append(mod)
    return entries


@pytest.mark.parametrize(
    "module_entry",
    _all_module_entries(),
    ids=lambda m: m["id"],
)
def test_module_importable(module_entry):
    """Each registered module class must be importable."""
    cls_str = module_entry["class"]
    module_path, class_name = cls_str.split(":")

    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)

    assert cls is not None
    assert isinstance(cls, type), f"{class_name} is not a class"
