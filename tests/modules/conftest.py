"""Module lifecycle conftest - fixtures for testing module classes."""

import pytest


@pytest.fixture
def all_module_entries():
    """Get all module entries from config (excluding internal sections)."""
    from app.core.config import ALL_MODULES
    return ALL_MODULES


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication for module tests."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def theme_manager(qapp):
    """Real ThemeManager instance for module tests."""
    from app.core.theme_manager import ThemeManager

    return ThemeManager()
