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
        self._worker_complete_cb = None
        self._worker_error_cb = None
        self.settings_manager = self._create_settings_manager()

    # ── Settings ─────────────────────────────────────────────────────

    def _create_settings_manager(self):
        """Create settings manager.

        Tries create_settings_manager() first (for custom manager classes),
        falls back to GenericSettingsManager from class attributes.
        """
        mgr = self.create_settings_manager()
        if mgr is not None:
            return mgr
        if hasattr(self, 'SETTINGS_FILENAME') and hasattr(self, 'DEFAULT_SETTINGS'):
            from app.services.base_settings_manager import GenericSettingsManager
            return GenericSettingsManager(self.SETTINGS_FILENAME, self.DEFAULT_SETTINGS)
        return None

    def create_settings_manager(self):
        """Override to return a custom settings manager instance."""
        return None

    def get_settings_options(self) -> list:
        """Return list of (key, label) for checkbox settings dialog."""
        return []

    def get_settings_dialog_title(self) -> str:
        """Title for the settings dialog."""
        return "Settings"

    def create_settings_dialog(self, current_settings):
        """Create and return a custom settings dialog.

        Only called if get_settings_options() returns empty list.
        Must return a dialog with exec() and get_settings() methods.
        """
        return None

    def _on_settings_clicked(self):
        """Open the settings dialog (checkbox or custom)."""
        if self.settings_manager is None:
            return
        from PySide6.QtWidgets import QDialog

        current_settings = self.settings_manager.get_all_settings()
        options = self.get_settings_options()

        if options:
            from app.ui.widgets.common.checkbox_settings_dialog import CheckboxSettingsDialog
            dialog = CheckboxSettingsDialog(
                self.theme_manager,
                title=self.get_settings_dialog_title(),
                options=options,
                current_settings=current_settings,
                parent=self,
            )
        else:
            dialog = self.create_settings_dialog(current_settings)
            if dialog is None:
                return

        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if new_settings:
                self.settings_manager.update_settings(new_settings)
                self._on_settings_changed(new_settings)

    def _on_settings_changed(self, new_settings):
        """Hook for post-settings-update logic. Override in subclass."""
        pass

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

    def _run_worker(self, fn, *args, loading_message="Loading...",
                    on_complete=None, on_error=None, **kwargs):
        """Run *fn* in a background QThread via CalculationWorker.

        Cancels any existing worker, shows loading overlay, and wires
        finished/error signals to *on_complete*/*on_error* (falling back
        to ``_on_worker_complete`` / ``_on_worker_error``).

        Callbacks are auto-wrapped to call ``_hide_loading()`` and
        ``_cleanup_worker()`` before invoking the callback, so callers
        do NOT need to call those themselves.

        Signals connect to bound methods on *self* (a QObject) so Qt's
        AutoConnection correctly queues delivery to the main thread.
        """
        from app.services.calculation_worker import CalculationWorker

        self._cancel_worker()
        self._show_loading(loading_message)

        self._worker_complete_cb = on_complete or self._on_worker_complete
        self._worker_error_cb = on_error or self._on_worker_error

        self._thread = QThread()
        self._worker = CalculationWorker(fn, *args, **kwargs)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_errored)

        self._thread.start()

        # Verify thread started (QThread.start() can fail silently)
        if not self._thread.isRunning():
            self._hide_loading()
            self._cleanup_worker()
            cb = self._worker_error_cb
            self._worker_complete_cb = None
            self._worker_error_cb = None
            if cb:
                cb("Failed to start background thread")

    def _on_worker_finished(self, result):
        """Internal slot for worker finished — always runs in main thread."""
        self._hide_loading()
        self._cleanup_worker()
        cb = self._worker_complete_cb
        self._worker_complete_cb = None
        self._worker_error_cb = None
        if cb:
            cb(result)

    def _on_worker_errored(self, error_msg):
        """Internal slot for worker error — always runs in main thread."""
        self._hide_loading()
        self._cleanup_worker()
        cb = self._worker_error_cb
        self._worker_complete_cb = None
        self._worker_error_cb = None
        if cb:
            cb(error_msg)

    def _on_worker_complete(self, result):
        """Default completion handler — subclasses should override."""
        pass

    def _on_worker_error(self, error_msg: str):
        """Default error handler — subclasses should override."""
        pass

    def _cleanup_worker(self):
        """Non-blocking cleanup: signal thread to quit, let it finish async.

        If the thread is stuck (e.g. yfinance timeout), it will be orphaned
        but won't block the UI. With network timeouts, orphaned threads will
        eventually terminate on their own.
        """
        if self._thread is not None:
            thread = self._thread
            worker = self._worker
            thread.quit()
            # Non-blocking: connect finished signal for deferred cleanup
            if worker is not None:
                thread.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
        self._worker = None
        self._thread = None

    def _cancel_worker(self):
        """Cancel any running worker with proper Qt cleanup."""
        if self._worker is not None:
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._worker_complete_cb = None
        self._worker_error_cb = None
        self._cleanup_worker()

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
