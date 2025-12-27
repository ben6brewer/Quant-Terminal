from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.core.config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
)
from app.ui.widgets.home_screen import HomeScreen


class TransparentOverlay(QWidget):
    """
    Transparent overlay widget that passes mouse events through except for its children.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event):
        """Pass mouse events through to widgets below unless clicking on a child widget."""
        # Check if click is on a child widget
        child_at_pos = self.childAt(event.pos())
        if child_at_pos:
            # Let child handle the event
            super().mousePressEvent(event)
        else:
            # Pass event through to widget below
            event.ignore()


class HubWindow(QMainWindow):
    """
    Main hub window with home screen and module navigation.
    Bloomberg terminal-inspired design with tile-based navigation.
    """

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Theme manager
        self.theme_manager = theme_manager
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

        # Module storage
        self.modules = {}
        self.module_containers = {}

        # Setup navigation
        self._setup_navigation()

        # Apply initial theme
        self._apply_theme()

    def _setup_navigation(self) -> None:
        """Setup dual-mode navigation (home screen + module views)."""
        # Main stack: home screen + module containers
        self.main_stack = QStackedWidget()
        self.setCentralWidget(self.main_stack)

        # Home screen (index 0)
        self.home_screen = HomeScreen(self.theme_manager)
        self.main_stack.addWidget(self.home_screen)

        # Connect home screen signals
        self.home_screen.module_selected.connect(self.open_module)
        self.home_screen.settings_requested.connect(self._open_settings)

    def add_module(self, module_id: str, widget: QWidget) -> None:
        """Add a module widget wrapped in container with home button."""
        # Create container with home button overlay
        container = self._create_module_container(widget)

        # Store references
        self.modules[module_id] = widget
        self.module_containers[module_id] = container

        # Add to stack
        self.main_stack.addWidget(container)

    def _create_module_container(self, module_widget: QWidget) -> QWidget:
        """Create container with home button overlay for module."""
        container = QWidget()
        layout = QStackedLayout(container)
        layout.setStackingMode(QStackedLayout.StackAll)
        layout.setContentsMargins(0, 0, 0, 0)

        # Layer 0: Module widget (full screen)
        layout.addWidget(module_widget)

        # Layer 1: Transparent overlay with home button (top-left)
        overlay = self._create_home_button_overlay()
        layout.addWidget(overlay)

        # CRITICAL FIX 3: Ensure overlay is on top
        overlay.raise_()

        return container

    def _create_home_button_overlay(self) -> QWidget:
        """Create transparent overlay with home button in top-left corner."""
        overlay = TransparentOverlay()

        # CRITICAL FIX 1: Force overlay to expand and fill container
        overlay.setSizePolicy(
            QSizePolicy.Expanding,  # Horizontal
            QSizePolicy.Expanding   # Vertical
        )

        # Set minimum size to ensure it's never collapsed
        overlay.setMinimumSize(100, 40)

        # Transparent background - overlay is invisible but passes events through
        overlay.setStyleSheet("background: transparent;")

        # Ensure overlay doesn't interfere with focus
        overlay.setFocusPolicy(Qt.NoFocus)

        # CRITICAL FIX 2: Don't align the layout, align the widget within it
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(10, 10, 0, 0)
        # REMOVED: layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)  # This caused shrinking!

        # Home button
        home_btn = QPushButton("🏠 Home")
        home_btn.setObjectName("homeButton")
        home_btn.setFixedSize(100, 40)
        home_btn.setCursor(Qt.PointingHandCursor)
        home_btn.clicked.connect(self.show_home)

        # Add button with alignment to position it top-left within the expanding layout
        layout.addWidget(home_btn, alignment=Qt.AlignTop | Qt.AlignLeft)
        layout.addStretch(1)

        return overlay

    def open_module(self, module_id: str) -> None:
        """Open a module in full screen."""
        if module_id not in self.module_containers:
            print(f"Warning: Module '{module_id}' not found")
            return

        container = self.module_containers[module_id]
        self.main_stack.setCurrentWidget(container)

    def show_home(self) -> None:
        """Return to home screen."""
        self.main_stack.setCurrentWidget(self.home_screen)
        self.home_screen.refresh()  # Reload favorites

    def show_initial_screen(self) -> None:
        """Show home screen on startup."""
        self.show_home()

    def _open_settings(self) -> None:
        """Open Settings module from home screen button."""
        self.open_module("settings")

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change signal."""
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply the current theme to the window."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Get complete dark theme stylesheet."""
        return (
            self.theme_manager.get_dark_content_style() +
            self.theme_manager.get_dark_home_button_style()
        )

    def _get_light_stylesheet(self) -> str:
        """Get complete light theme stylesheet."""
        return (
            self.theme_manager.get_light_content_style() +
            self.theme_manager.get_light_home_button_style()
        )
