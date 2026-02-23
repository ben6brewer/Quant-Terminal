from __future__ import annotations

from typing import Callable
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QPushButton


class ThemeManager(QObject):
    """
    Centralized theme management for the application.
    Provides consistent theming across all modules and widgets.
    Automatically saves theme preferences to disk.

    Stylesheet generation is delegated to ThemeStylesheetService.
    """

    theme_changed = Signal(str)  # Emits the new theme name

    def __init__(self):
        super().__init__()
        self._current_theme = "bloomberg"  # Default if not loaded from preferences
        self._theme_listeners = []
        self._styled_buttons = []  # Track buttons for theme updates

    @property
    def current_theme(self) -> str:
        """Get the current active theme."""
        return self._current_theme

    def set_theme(self, theme: str, save_preference: bool = True) -> None:
        """
        Set the application theme.

        Args:
            theme: Either "dark", "light", or "bloomberg"
            save_preference: Whether to save the theme preference to disk (default: True)
        """
        if theme not in ("dark", "light", "bloomberg"):
            raise ValueError(f"Unknown theme: {theme}. Must be 'dark', 'light', or 'bloomberg'.")

        if theme == self._current_theme:
            return

        self._current_theme = theme

        # Emit signal immediately so UI can respond
        self.theme_changed.emit(theme)

        # Defer button updates to avoid blocking the UI thread
        QTimer.singleShot(0, self._update_styled_buttons)

        # Save preference to disk
        if save_preference:
            from app.services.preferences_service import PreferencesService
            PreferencesService.set_theme(theme)

    def _update_styled_buttons(self) -> None:
        """Apply current theme styling to all tracked buttons (deferred)."""
        from app.services.theme_stylesheet_service import ThemeStylesheetService

        universal_style = ThemeStylesheetService.get_button_stylesheet(self._current_theme)
        # Filter out destroyed buttons and update valid ones
        valid_buttons = []
        for button in self._styled_buttons:
            try:
                # Try to access the button - will raise if deleted
                if button and button.isVisible is not None:
                    button.setStyleSheet(universal_style)
                    valid_buttons.append(button)
            except RuntimeError:
                # Button was deleted, skip it
                pass
        self._styled_buttons = valid_buttons

    def register_listener(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback to be notified of theme changes.

        Args:
            callback: Function that takes theme name as argument
        """
        self._theme_listeners.append(callback)
        self.theme_changed.connect(callback)

    def unregister_listener(self, callback: Callable[[str], None]) -> None:
        """Unregister a theme change callback."""
        if callback in self._theme_listeners:
            self._theme_listeners.remove(callback)
            self.theme_changed.disconnect(callback)

    # ------------------------------------------------------------------
    # Convenience wrappers (delegate to ThemeStylesheetService)
    # ------------------------------------------------------------------

    def get_controls_stylesheet(self) -> str:
        """Get controls stylesheet for current theme."""
        from app.services.theme_stylesheet_service import ThemeStylesheetService
        return ThemeStylesheetService.get_controls_stylesheet(self._current_theme)

    def get_home_button_style(self) -> str:
        """Get home button stylesheet for current theme."""
        from app.services.theme_stylesheet_service import ThemeStylesheetService
        return ThemeStylesheetService.get_home_button_stylesheet(self._current_theme)

    def get_chart_background_color(self) -> str:
        """Get chart background color for current theme."""
        from app.services.theme_stylesheet_service import ThemeStylesheetService
        return ThemeStylesheetService.get_chart_background_color(self._current_theme)

    def get_chart_line_color(self) -> tuple[int, int, int]:
        """Get chart line color for current theme."""
        from app.services.theme_stylesheet_service import ThemeStylesheetService
        return ThemeStylesheetService.get_chart_line_color(self._current_theme)

    def create_styled_button(self, text: str, checkable: bool = False) -> QPushButton:
        """
        Create a button with universal styling applied.

        Args:
            text: Button text
            checkable: If True, button is checkable (toggle button)

        Returns:
            QPushButton with styling applied and tracked for theme updates
        """
        from app.services.theme_stylesheet_service import ThemeStylesheetService

        button = QPushButton(text)
        button.setCheckable(checkable)
        stylesheet = ThemeStylesheetService.get_button_stylesheet(self._current_theme)
        button.setStyleSheet(stylesheet)

        # Track for theme updates
        self._styled_buttons.append(button)

        return button
