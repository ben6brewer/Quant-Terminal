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
from PySide6.QtGui import QFont


class HubWindow(QMainWindow):
    """
    Main hub window with sidebar navigation to different modules.
    Bloomberg terminal-inspired design.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quant Terminal")
        self.resize(1400, 900)

        # Theme state
        self.current_theme = "dark"

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
        self.set_theme("dark")

    def _create_sidebar(self) -> QWidget:
        """Create the navigation sidebar."""
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setObjectName("sidebar")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("QUANT TERMINAL")
        header.setObjectName("sidebarHeader")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Navigation buttons
        nav_data = [
            ("📊 Charts", "charts"),
            ("💼 Portfolio", "portfolio"),
            ("👁 Watchlist", "watchlist"),
            ("📰 News", "news"),
            ("🔍 Screener", "screener"),
            ("📈 Analysis", "analysis"),
            ("⚙️ Settings", "settings"),
        ]

        self.nav_buttons = {}
        for label, module_id in nav_data:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("navButton")
            btn.clicked.connect(lambda checked, mid=module_id: self.switch_module(mid))
            layout.addWidget(btn)
            self.nav_buttons[module_id] = btn

        layout.addStretch(1)

        # Footer info
        footer = QLabel("v0.1.0")
        footer.setObjectName("sidebarFooter")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        return sidebar

    def set_theme(self, theme: str) -> None:
        """Apply a theme to the entire application."""
        self.current_theme = theme

        if theme == "light":
            stylesheet = self._get_light_theme()
        else:
            stylesheet = self._get_dark_theme()

        self.setStyleSheet(stylesheet)

        # Propagate theme to chart module if it exists
        if "charts" in self.modules:
            chart_module = self.modules["charts"]
            if hasattr(chart_module, "set_theme"):
                chart_module.set_theme(theme)

    def _get_dark_theme(self) -> str:
        """Get dark theme stylesheet."""
        return """
            /* Sidebar */
            #sidebar {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            
            #sidebarHeader {
                background-color: #1a1a1a;
                color: #00d4ff;
                font-size: 14px;
                font-weight: bold;
                padding: 20px 10px;
                border-bottom: 2px solid #00d4ff;
            }
            
            #sidebarFooter {
                color: #666666;
                font-size: 10px;
                padding: 10px;
            }
            
            #navButton {
                text-align: left;
                padding: 15px 20px;
                border: none;
                background-color: transparent;
                color: #cccccc;
                font-size: 13px;
                font-weight: 500;
            }
            
            #navButton:hover {
                background-color: #3d3d3d;
                color: #ffffff;
            }
            
            #navButton:checked {
                background-color: #00d4ff;
                color: #000000;
                font-weight: bold;
            }
            
            /* Content area */
            QStackedWidget {
                background-color: #1e1e1e;
            }
            
            /* Settings module */
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            
            QGroupBox {
                color: #ffffff;
                background-color: #2d2d2d;
            }
            
            QLabel {
                color: #cccccc;
            }
            
            QRadioButton {
                color: #cccccc;
            }
            
            /* Placeholder modules */
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """

    def _get_light_theme(self) -> str:
        """Get light theme stylesheet."""
        return """
            /* Sidebar */
            #sidebar {
                background-color: #f5f5f5;
                color: #000000;
            }
            
            #sidebarHeader {
                background-color: #e0e0e0;
                color: #0066cc;
                font-size: 14px;
                font-weight: bold;
                padding: 20px 10px;
                border-bottom: 2px solid #0066cc;
            }
            
            #sidebarFooter {
                color: #999999;
                font-size: 10px;
                padding: 10px;
            }
            
            #navButton {
                text-align: left;
                padding: 15px 20px;
                border: none;
                background-color: transparent;
                color: #333333;
                font-size: 13px;
                font-weight: 500;
            }
            
            #navButton:hover {
                background-color: #e8e8e8;
                color: #000000;
            }
            
            #navButton:checked {
                background-color: #0066cc;
                color: #ffffff;
                font-weight: bold;
            }
            
            /* Content area */
            QStackedWidget {
                background-color: #ffffff;
            }
            
            /* Settings module */
            QScrollArea {
                background-color: #ffffff;
                border: none;
            }
            
            QGroupBox {
                color: #000000;
                background-color: #f5f5f5;
                border: 2px solid #d0d0d0;
            }
            
            QLabel {
                color: #333333;
            }
            
            QRadioButton {
                color: #333333;
            }
            
            /* Placeholder modules */
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
        """

    @staticmethod
    def _get_nav_button_style() -> str:
        return """
            QPushButton {
                text-align: left;
                padding: 15px 20px;
                border: none;
                background-color: transparent;
                color: #cccccc;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #00d4ff;
                color: #000000;
                font-weight: bold;
            }
        """

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