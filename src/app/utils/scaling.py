"""Screen-aware scaling utilities for cross-platform responsive UI."""

from __future__ import annotations

# Reference resolution (1920x1080 Windows)
_REF_WIDTH = 1920
_REF_HEIGHT = 1080

# Cache
_scale_factor: float | None = None


def get_scale_factor() -> float:
    """
    Return a scale factor based on primary screen size vs 1920x1080 reference.

    Cached after first call. Clamped to 0.65-1.5 range.
    On a 1440x900 Mac, this returns ~0.75.
    On a 1920x1080 Windows, this returns ~1.0.
    """
    global _scale_factor
    if _scale_factor is not None:
        return _scale_factor

    from PySide6.QtWidgets import QApplication

    screen = QApplication.primaryScreen()
    if screen is None:
        _scale_factor = 1.0
        return _scale_factor

    geom = screen.availableGeometry()
    w_ratio = geom.width() / _REF_WIDTH
    h_ratio = geom.height() / _REF_HEIGHT
    raw = min(w_ratio, h_ratio)

    _scale_factor = max(0.65, min(1.5, raw))
    return _scale_factor


def scaled(px: int) -> int:
    """Scale a pixel value by the screen scale factor."""
    return int(px * get_scale_factor())
