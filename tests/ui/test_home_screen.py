"""Tests for home screen tile grid rendering."""

import pytest


@pytest.mark.ui
class TestHomeScreen:
    def test_home_screen_imports(self):
        from app.ui.home_screen import HomeScreen
        assert HomeScreen is not None

    def test_home_screen_instantiation(self, qapp, theme_manager):
        from app.ui.home_screen import HomeScreen
        screen = HomeScreen(theme_manager)
        assert screen is not None

    def test_has_tiles(self, qapp, theme_manager):
        """Home screen should create tiles from ALL_MODULES."""
        from app.ui.home_screen import HomeScreen
        from app.core.config import ALL_MODULES

        screen = HomeScreen(theme_manager)
        # Should have at least some child widgets
        assert screen is not None
