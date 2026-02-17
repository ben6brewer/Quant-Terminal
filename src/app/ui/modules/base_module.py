"""Base module class - shared infrastructure for all Quant Terminal modules."""

from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, QThread

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class BaseModule(LazyThemeMixin, QWidget):
    """
    Base class for all Quant Terminal modules.

    Provides shared infrastructure:
    - Loading overlay lifecycle (show/hide/resize)
    - Theme background application via ThemeStylesheetService
    - Worker thread lifecycle (cleanup/cancel)
    - home_clicked signal
    - showEvent/hideEvent boilerplate for lazy theming and worker cleanup
    """

    home_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._loading_overlay = None
        self._worker = None
        self._thread: Optional[QThread] = None

    # ── Loading Overlay ──────────────────────────────────────────────

    def _show_loading(self, message: str = "Loading..."):
        from app.ui.widgets.common.loading_overlay import LoadingOverlay

        if self._loading_overlay is None:
            self._loading_overlay = LoadingOverlay(self, self.theme_manager, message)
        else:
            self._loading_overlay.set_message(message)
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    def _hide_loading(self):
        if self._loading_overlay:
            self._loading_overlay.hide()

    # ── Worker Thread Lifecycle ──────────────────────────────────────

    def _cleanup_worker(self):
        """Safely stop thread and release references."""
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None

    def _cancel_worker(self):
        """Cancel any running worker with timeout."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self._worker = None
        self._thread = None

    # ── Theme ────────────────────────────────────────────────────────

    def _get_theme_bg(self) -> str:
        """Get the background color for the current theme."""
        from app.services.theme_stylesheet_service import ThemeStylesheetService

        colors = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
        return colors["bg"]

    def _apply_theme(self):
        """Apply theme background. Override for additional theme logic."""
        self.setStyleSheet(f"background-color: {self._get_theme_bg()};")

    # ── Events ───────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def hideEvent(self, event):
        self._cancel_worker()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._loading_overlay:
            self._loading_overlay.resize(self.size())
