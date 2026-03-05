"""Tests for app.utils.scaling."""

from unittest.mock import MagicMock, patch

import pytest


class TestGetScaleFactor:
    def setup_method(self):
        """Reset cached scale factor between tests."""
        import app.utils.scaling as scaling_mod
        scaling_mod._scale_factor = None

    def test_returns_float(self):
        """Scale factor should be a float."""
        from app.utils.scaling import get_scale_factor

        factor = get_scale_factor()
        assert isinstance(factor, float)

    def test_clamped_range(self):
        """Scale factor should be between 0.65 and 1.5."""
        from app.utils.scaling import get_scale_factor

        factor = get_scale_factor()
        assert 0.65 <= factor <= 1.5

    def test_caching(self):
        """Second call returns cached value."""
        import app.utils.scaling as scaling_mod
        from app.utils.scaling import get_scale_factor

        f1 = get_scale_factor()
        f2 = get_scale_factor()
        assert f1 == f2

    def test_no_screen_fallback(self):
        """If no screen available, return 1.0."""
        import app.utils.scaling as scaling_mod
        scaling_mod._scale_factor = None

        with patch("PySide6.QtWidgets.QApplication") as mock_app:
            mock_app.primaryScreen.return_value = None
            from app.utils.scaling import get_scale_factor
            # Reset again since import may have cached
            scaling_mod._scale_factor = None
            factor = get_scale_factor()
            assert factor == 1.0


class TestScaled:
    def test_basic(self):
        """scaled() should multiply by scale factor and return int."""
        import app.utils.scaling as scaling_mod
        scaling_mod._scale_factor = 0.75

        from app.utils.scaling import scaled

        assert scaled(100) == 75

    def test_unity(self):
        import app.utils.scaling as scaling_mod
        scaling_mod._scale_factor = 1.0

        from app.utils.scaling import scaled

        assert scaled(100) == 100

    def test_rounding(self):
        import app.utils.scaling as scaling_mod
        scaling_mod._scale_factor = 0.75

        from app.utils.scaling import scaled

        assert isinstance(scaled(33), int)
