from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from app.core.theme_manager import ThemeManager
from app.core.config import APP_NAME, APP_VERSION


class ModuleTile(QFrame):
    """A clickable tile representing a module."""
    
    clicked = Signal(str)  # Emits module_id when clicked
    
    def __init__(self, icon: str, title: str, description: str, module_id: str, parent=None):
        super().__init__(parent)
        self.module_id = module_id
        self.setObjectName("moduleTile")
        self.setCursor(Qt.PointingHandCursor)
        
        # Make it focusable and clickable
        self.setFocusPolicy(Qt.StrongFocus)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Icon (emoji)
        icon_label = QLabel(icon)
        icon_label.setObjectName("tileIcon")
        icon_font = QFont()
        icon_font.setPointSize(48)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        title_label.setObjectName("tileTitle")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setObjectName("tileDescription")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        layout.addStretch()
    
    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.module_id)
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        """Change appearance on hover."""
        self.setProperty("hover", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Restore appearance when not hovering."""
        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)


class HomeScreen(QWidget):
    """
    Home screen with module tiles.
    Displays available modules as clickable cards.
    """
    
    module_selected = Signal(str)  # Emits module_id when a module is selected
    
    # Module definitions (icon, title, description, module_id)
    MODULES = [
        ("📊", "Charts", "Technical analysis with indicators", "charts"),
        ("💼", "Portfolio", "Track investments and performance", "portfolio"),
        ("👁", "Watchlist", "Monitor favorite securities", "watchlist"),
        ("📰", "News", "Latest market news and research", "news"),
        ("🔍", "Screener", "Discover stocks by criteria", "screener"),
        ("📈", "Analysis", "In-depth analysis tools", "analysis"),
        ("⚙️", "Settings", "Customize your experience", "settings"),
    ]
    
    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()
        self._apply_theme()
        
        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _setup_ui(self):
        """Create the home screen UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        # Header section
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        
        # App title
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        title_font = QFont()
        title_font.setPointSize(36)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Professional Trading & Analysis Platform")
        subtitle.setObjectName("appSubtitle")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle.setFont(subtitle_font)
        subtitle.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(subtitle)
        
        layout.addLayout(header_layout)
        layout.addSpacing(20)
        
        # Module tiles grid
        grid = QGridLayout()
        grid.setSpacing(20)
        
        # Create tiles in a grid (3 columns)
        row = 0
        col = 0
        for icon, title, description, module_id in self.MODULES:
            tile = ModuleTile(icon, title, description, module_id)
            tile.clicked.connect(self.module_selected.emit)
            grid.addWidget(tile, row, col)
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        layout.addLayout(grid)
        layout.addStretch()
        
        # Footer with version
        footer = QLabel(f"Version {APP_VERSION}")
        footer.setObjectName("versionLabel")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)
    
    def _on_theme_changed(self, theme: str):
        """Handle theme change."""
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply current theme styling."""
        theme = self.theme_manager.current_theme
        
        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()
        
        self.setStyleSheet(stylesheet)
    
    def _get_dark_stylesheet(self) -> str:
        """Get dark theme stylesheet."""
        return """
            HomeScreen {
                background-color: #1e1e1e;
            }
            
            #appTitle {
                color: #00d4ff;
            }
            
            #appSubtitle {
                color: #cccccc;
            }
            
            #versionLabel {
                color: #666666;
                font-size: 11px;
            }
            
            #moduleTile {
                background-color: #2d2d2d;
                border: 2px solid #3d3d3d;
                border-radius: 12px;
                min-width: 200px;
                min-height: 220px;
            }
            
            #moduleTile[hover="true"] {
                background-color: #3d3d3d;
                border: 2px solid #00d4ff;
            }
            
            #tileIcon {
                color: #00d4ff;
            }
            
            #tileTitle {
                color: #ffffff;
            }
            
            #tileDescription {
                color: #cccccc;
                font-size: 12px;
            }
        """
    
    def _get_light_stylesheet(self) -> str:
        """Get light theme stylesheet."""
        return """
            HomeScreen {
                background-color: #ffffff;
            }
            
            #appTitle {
                color: #0066cc;
            }
            
            #appSubtitle {
                color: #333333;
            }
            
            #versionLabel {
                color: #999999;
                font-size: 11px;
            }
            
            #moduleTile {
                background-color: #f5f5f5;
                border: 2px solid #d0d0d0;
                border-radius: 12px;
                min-width: 200px;
                min-height: 220px;
            }
            
            #moduleTile[hover="true"] {
                background-color: #e8e8e8;
                border: 2px solid #0066cc;
            }
            
            #tileIcon {
                color: #0066cc;
            }
            
            #tileTitle {
                color: #000000;
            }
            
            #tileDescription {
                color: #666666;
                font-size: 12px;
            }
        """