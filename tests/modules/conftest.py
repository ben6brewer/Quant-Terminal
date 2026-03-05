"""Module lifecycle conftest - fixtures for testing module classes."""

import pytest


@pytest.fixture
def all_module_entries():
    """Get all module entries from config (excluding internal sections)."""
    from app.core.config import ALL_MODULES
    return ALL_MODULES
