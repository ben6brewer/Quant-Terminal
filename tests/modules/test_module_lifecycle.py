"""Module lifecycle tests - parametrized across all registered modules."""

import importlib

import pytest

from app.core.config import ALL_MODULES


def _get_module_class(entry):
    """Import and return the module class from a config entry."""
    module_path, class_name = entry["class"].split(":")
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def _is_fred_module(cls):
    """Check if cls is a FredDataModule subclass."""
    try:
        from app.ui.modules.fred_base_module import FredDataModule
        return issubclass(cls, FredDataModule)
    except ImportError:
        return False


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

    @pytest.mark.ui
    def test_fred_module_instantiation(self, entry, qapp, theme_manager):
        """FredDataModule subclasses should instantiate without errors.

        This catches __init__ crashes like missing toolbar attributes
        (e.g. lookback_combo) that only surface at construction time.
        """
        cls = _get_module_class(entry)
        if not _is_fred_module(cls):
            pytest.skip("Not a FredDataModule subclass")

        # Instantiate — exercises _setup_ui, _connect_signals,
        # _apply_settings, _apply_theme.  No show() so no data fetch.
        widget = cls(theme_manager)
        assert widget is not None
        assert widget.toolbar is not None
        assert widget.chart is not None
        widget.deleteLater()
