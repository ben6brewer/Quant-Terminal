"""Tests for app.core.config integrity."""

import pytest

from app.core.config import ALL_MODULES, MODULE_SECTIONS


class TestModuleSections:
    def test_sections_not_empty(self):
        assert len(MODULE_SECTIONS) > 0

    def test_all_modules_populated(self):
        assert len(ALL_MODULES) > 0

    def test_unique_ids(self):
        """All module IDs must be unique."""
        ids = [m["id"] for m in ALL_MODULES]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_required_keys(self):
        """Every module entry must have id, label, and class keys."""
        for section_name, modules in MODULE_SECTIONS.items():
            for mod in modules:
                assert "id" in mod, f"Missing 'id' in {section_name}: {mod}"
                assert "label" in mod, f"Missing 'label' in {section_name}: {mod}"
                assert "class" in mod, f"Missing 'class' in {section_name}: {mod}"

    def test_class_format(self):
        """Class strings must be 'dotted.path:ClassName' format."""
        for mod in ALL_MODULES:
            cls_str = mod["class"]
            assert ":" in cls_str, f"Invalid class format for {mod['id']}: {cls_str}"
            module_path, class_name = cls_str.split(":")
            assert "." in module_path, f"Module path should be dotted for {mod['id']}"
            assert class_name[0].isupper(), f"Class name should be PascalCase for {mod['id']}"

    def test_internal_sections_excluded(self):
        """ALL_MODULES should exclude sections starting with '_'."""
        for mod in ALL_MODULES:
            assert mod["id"] != "settings", "Settings should be excluded from ALL_MODULES"

    def test_sections_have_expected_names(self):
        """Check that expected section names exist."""
        section_names = set(MODULE_SECTIONS.keys())
        assert "Charting" in section_names
        assert "Portfolio" in section_names
        assert "Analysis" in section_names
        assert "Macro" in section_names

    def test_at_least_28_modules(self):
        """Verify we have at least 28 public modules."""
        assert len(ALL_MODULES) >= 28
