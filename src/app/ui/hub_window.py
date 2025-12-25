from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
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
    SIDEBAR_WIDTH,
    NAVIGATION_MODULES,
)


class HubWindow(QMainWindow):
    """
    Main hub window with sidebar navigation to different modules.
    Bloomberg terminal-inspired design.
    """

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Theme manager
        self.theme_manager = theme_manager
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

        # Main widget
        central = QWidget(self)
        self.setCentralWidget(central)

        # Horizontal layout: sidebar | content
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar ---
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)

        # --- Content area (stacked widget for different modules) ---
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, stretch=1)

        # Module widgets will be added here
        self.modules = {}

        # Apply initial theme
        self._apply_theme()

    def _create_sidebar(self) -> QWidget:
        """Create the navigation sidebar."""
        sidebar = QWidget()
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setObjectName("sidebar")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel(APP_NAME.upper())
        header.setObjectName("sidebarHeader")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Navigation buttons
        self.nav_buttons = {}
        for label, module_id in NAVIGATION_MODULES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("navButton")
            btn.clicked.connect(lambda checked, mid=module_id: self.switch_module(mid))
            layout.addWidget(btn)
            self.nav_buttons[module_id] = btn

        layout.addStretch(1)

        # Footer info
        footer = QLabel(f"v{APP_VERSION}")
        footer.setObjectName("sidebarFooter")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        return sidebar

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
            self.theme_manager.get_dark_sidebar_style() +
            self.theme_manager.get_dark_content_style()
        )

    def _get_light_stylesheet(self) -> str:
        """Get complete light theme stylesheet."""
        return (
            self.theme_manager.get_light_sidebar_style() +
            self.theme_manager.get_light_content_style()
        )

    def add_module(self, module_id: str, widget: QWidget) -> None:
        """Add a module widget to the hub."""
        self.modules[module_id] = widget
        self.content_stack.addWidget(widget)

    def switch_module(self, module_id: str) -> None:
        """Switch to a specific module."""
        if module_id not in self.modules:
            return

        # Update button states
        for btn_id, btn in self.nav_buttons.items():
            btn.setChecked(btn_id == module_id)

        # Switch content
        widget = self.modules[module_id]
        self.content_stack.setCurrentWidget(widget)

    def show_initial_module(self, module_id: str = "charts") -> None:
        """Show a specific module on startup."""
        if module_id in self.modules:
            self.switch_module(module_id)
