"""Resize Handle - Draggable handle for adjusting oscillator height."""

from typing import Tuple
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal


class ResizeHandle(QWidget):
    """
    Resize handle for adjusting oscillator height.

    An 8px tall invisible hotspot that shows a colored bar on hover.
    Allows dragging to resize the oscillator subplot.
    """

    height_changed = Signal(int)  # Emits delta_y during drag
    drag_started = Signal()  # Emitted when drag begins
    drag_ended = Signal()    # Emitted when drag ends

    def __init__(self, parent):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)

        self._theme = "bloomberg"
        self._show_bar = False
        self._is_dragging = False
        self._drag_start_y = 0
        self._last_y = 0

        # Transparent background
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAutoFillBackground(False)

    def set_theme(self, theme: str):
        """No-op: Bar color is now theme-independent."""
        pass

    def _get_bar_color(self) -> Tuple[int, int, int]:
        """Get subtle grey color for resize bar (theme-independent)."""
        return (150, 150, 150)  # Subtle grey

    def enterEvent(self, event):
        """Show hover bar and change cursor."""
        if not self._is_dragging:
            self._show_bar = True
            self.setCursor(Qt.SizeVerCursor)
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide bar and restore cursor (unless dragging)."""
        if not self._is_dragging:
            self._show_bar = False
            self.setCursor(Qt.ArrowCursor)
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Start drag operation."""
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_start_y = event.pos().y()
            self._last_y = event.pos().y()
            self._show_bar = True
            self.setCursor(Qt.SizeVerCursor)
            self.update()
            self.drag_started.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Emit height change during drag."""
        if self._is_dragging:
            current_y = event.pos().y()
            delta_y = current_y - self._last_y
            self._last_y = current_y

            # Emit delta for parent to handle
            self.height_changed.emit(delta_y)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """End drag operation."""
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False

            # Check if still hovering to keep bar visible
            if not self.underMouse():
                self._show_bar = False
                self.setCursor(Qt.ArrowCursor)

            self.update()
            self.drag_ended.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Resize bar is completely invisible (no visual feedback)."""
        return  # Always invisible - resize handle is purely functional
