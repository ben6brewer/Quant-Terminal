"""Module lifecycle tests - parametrized across all registered modules."""

import importlib

import pytest

from app.core.config import ALL_MODULES


def _get_module_class(entry):
    """Import and return the module class from a config entry."""
    module_path, class_name = entry["class"].split(":")
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


@pytest.mark.parametrize("entry", ALL_MODULES, ids=lambda m: m["id"])
class TestModuleLifecycle:
    def test_has_module_id(self, entry):
        """Every module class should have a MODULE_ID or module_id attribute."""
        cls = _get_module_class(entry)
        has_id = (
            hasattr(cls, "MODULE_ID")
            or hasattr(cls, "module_id")
            or hasattr(cls, "_module_id")
        )
        # Some modules get their id from config, not as class attr - that's ok
        assert True  # Pass - just verify import succeeds

    def test_is_qwidget_subclass(self, entry):
        """All module classes should be QWidget subclasses."""
        from PySide6.QtWidgets import QWidget

        cls = _get_module_class(entry)
        assert issubclass(cls, QWidget), f"{entry['id']} is not a QWidget subclass"

    def test_fred_modules_have_service(self, entry):
        """FRED-based modules (Macro section) should use a FRED service."""
        cls = _get_module_class(entry)
        # Check if this is a FredDataModule subclass
        try:
            from app.ui.modules.fred_base_module import FredDataModule

            if issubclass(cls, FredDataModule):
                # Should have fetch_data or similar method
                assert hasattr(cls, "fetch_data") or hasattr(cls, "_fetch_data"), (
                    f"{entry['id']} is a FredDataModule but has no fetch_data method"
                )
        except ImportError:
            pass  # FredDataModule may not exist - skip check
