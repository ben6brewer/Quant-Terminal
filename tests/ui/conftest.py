"""UI conftest - QApplication session fixture and real ThemeManager."""

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication for UI tests."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


# qtbot is provided by pytest-qt automatically — no need to redefine it


@pytest.fixture
def theme_manager(qapp):
    """Real ThemeManager instance for UI tests."""
    from app.core.theme_manager import ThemeManager

    tm = ThemeManager()
    return tm
