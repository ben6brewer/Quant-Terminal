"""Tests for app.ui.widgets.charting.base_chart.BaseChart."""

import pytest


@pytest.mark.ui
class TestBaseChart:
    @pytest.fixture
    def chart(self, qapp):
        from app.ui.widgets.charting.base_chart import BaseChart
        return BaseChart()

    def test_instantiation(self, chart):
        assert chart is not None

    def test_default_theme(self, chart):
        assert chart._theme == "dark"

    def test_set_theme(self, chart):
        chart.set_theme("bloomberg")
        assert chart._theme == "bloomberg"

    def test_background_rgb(self, chart):
        rgb = chart._get_background_rgb()
        assert isinstance(rgb, tuple)
        assert len(rgb) == 3
        assert all(0 <= c <= 255 for c in rgb)

    def test_theme_changes_background(self, chart):
        chart.set_theme("dark")
        dark_bg = chart._get_background_rgb()
        chart.set_theme("light")
        light_bg = chart._get_background_rgb()
        assert dark_bg != light_bg

    def test_luminance_calculation(self, chart):
        # White = high luminance
        lum_white = chart._calculate_relative_luminance((255, 255, 255))
        assert lum_white > 0.9
        # Black = low luminance
        lum_black = chart._calculate_relative_luminance((0, 0, 0))
        assert lum_black < 0.01
