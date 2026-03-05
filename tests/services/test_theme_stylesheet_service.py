"""Tests for app.services.theme_stylesheet_service.ThemeStylesheetService."""

import pytest

from app.services.theme_stylesheet_service import ThemeStylesheetService


class TestGetColors:
    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_returns_dict(self, theme):
        colors = ThemeStylesheetService.get_colors(theme)
        assert isinstance(colors, dict)
        assert len(colors) > 0

    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_has_essential_keys(self, theme):
        colors = ThemeStylesheetService.get_colors(theme)
        # Should have background and text colors at minimum
        assert any("bg" in k.lower() or "background" in k.lower() for k in colors)


class TestStylesheetGeneration:
    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_table_stylesheet(self, theme):
        css = ThemeStylesheetService.get_table_stylesheet(theme)
        assert isinstance(css, str)
        assert len(css) > 0

    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_dialog_stylesheet(self, theme):
        css = ThemeStylesheetService.get_dialog_stylesheet(theme)
        assert isinstance(css, str)
        assert "QDialog" in css or "background" in css

    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_toolbar_stylesheet(self, theme):
        css = ThemeStylesheetService.get_toolbar_stylesheet(theme)
        assert isinstance(css, str)
        assert len(css) > 0

    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_button_stylesheet(self, theme):
        css = ThemeStylesheetService.get_button_stylesheet(theme)
        assert isinstance(css, str)

    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_sidebar_stylesheet(self, theme):
        css = ThemeStylesheetService.get_sidebar_stylesheet(theme)
        assert isinstance(css, str)


class TestColorAccessors:
    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_background_rgb(self, theme):
        rgb = ThemeStylesheetService.get_background_rgb(theme)
        assert isinstance(rgb, tuple)
        assert len(rgb) == 3
        assert all(0 <= c <= 255 for c in rgb)

    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_text_rgb(self, theme):
        rgb = ThemeStylesheetService.get_text_rgb(theme)
        assert isinstance(rgb, tuple)
        assert len(rgb) == 3

    @pytest.mark.parametrize("theme", ["dark", "light", "bloomberg"])
    def test_accent_rgb(self, theme):
        rgb = ThemeStylesheetService.get_accent_rgb(theme)
        assert isinstance(rgb, tuple)
        assert len(rgb) == 3
