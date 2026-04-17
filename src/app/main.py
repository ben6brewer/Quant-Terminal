from __future__ import annotations

# Install compatibility shims (distutils for Py3.12+, deprecate_kwarg for
# pandas 3.x) BEFORE any module that may transitively import
# pandas_datareader. Must come before all other imports.
from app import _compat  # noqa: F401  (imported for side effects)

import importlib
import multiprocessing
import signal
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.ui.hub_window import HubWindow
from app.core.theme_manager import ThemeManager
from app.core.config import DEFAULT_THEME, MODULE_SECTIONS
from app.services.favorites_service import FavoritesService
from app.services.preferences_service import PreferencesService


def _dynamic_import(class_path: str):
    """Import a class from a 'dotted.module.path:ClassName' string."""
    module_path, class_name = class_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def main() -> int:
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)

    # Initialize services
    FavoritesService.initialize()
    PreferencesService.initialize()

    # Create centralized theme manager and load saved theme
    theme_manager = ThemeManager()
    saved_theme = PreferencesService.get_theme()
    theme_manager.set_theme(saved_theme, save_preference=False)  # Don't re-save on load

    # Create main hub window with theme manager
    hub = HubWindow(theme_manager)

    # Register all modules from config — lazy loading via importlib
    for section_modules in MODULE_SECTIONS.values():
        for entry in section_modules:
            cp = entry["class"]
            hub.add_module(
                entry["id"],
                lambda cp=cp: _dynamic_import(cp)(theme_manager),
                has_own_home_button=entry.get("has_own_home_button", True),
            )

    # Show home screen on startup
    hub.show_initial_screen()

    # Show window and manually maximize (critical for frameless windows on Windows)
    # DO NOT use showMaximized() - it locks geometry and prevents restore button from working
    hub.show()
    hub.maximize_on_startup()

    # Fix: install SIGINT handler so Ctrl+C (and spurious macOS SIGINTs) quit
    # cleanly instead of raising KeyboardInterrupt inside Qt C++ callbacks
    signal.signal(signal.SIGINT, lambda *args: app.quit())

    # Qt's C++ event loop doesn't give Python a chance to check for pending
    # signals between C++ calls. This no-op timer wakes Python every 200ms so
    # signal delivery happens at a safe time (not mid-Qt-callback).
    _signal_timer = QTimer()
    _signal_timer.start(200)
    _signal_timer.timeout.connect(lambda: None)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
