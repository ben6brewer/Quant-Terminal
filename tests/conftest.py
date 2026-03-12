"""Root conftest - shared fixtures and --full flag handling."""

import pytest


@pytest.fixture(autouse=True, scope="session")
def protect_fred_api_key():
    """Save/restore the real FRED API key around the entire test session."""
    from app.services.fred_api_key_service import FredApiKeyService

    original = FredApiKeyService._api_key
    yield
    FredApiKeyService._api_key = original


def pytest_addoption(parser):
    parser.addoption(
        "--full",
        action="store_true",
        default=False,
        help="Run full test suite including UI tests",
    )


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.ui tests unless --full is passed."""
    if config.getoption("--full"):
        return
    skip_ui = pytest.mark.skip(reason="UI tests require --full flag")
    for item in items:
        if "ui" in item.keywords:
            item.add_marker(skip_ui)


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Isolated temp directory for cache tests."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def tmp_settings_dir(tmp_path):
    """Isolated temp directory for settings tests."""
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    return settings_dir


@pytest.fixture
def mock_theme_manager():
    """MagicMock ThemeManager with .current_theme and .theme_changed signal."""
    from unittest.mock import MagicMock

    tm = MagicMock()
    tm.current_theme = "bloomberg"
    tm.theme_changed = MagicMock()
    tm.theme_changed.connect = MagicMock()
    return tm
