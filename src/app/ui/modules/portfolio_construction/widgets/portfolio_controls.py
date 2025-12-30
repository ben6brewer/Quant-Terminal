"""Portfolio Controls Widget - Top Control Bar"""

from typing import List
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager


class PortfolioControls(QWidget):
    """
    Control bar at top of portfolio module.
    Contains: Home button, Portfolio selector, New/Save (transaction view only).
    """

    # Signals
    home_clicked = Signal()
    portfolio_changed = Signal(str)       # Portfolio name changed
    save_clicked = Signal()
    new_portfolio_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        self._setup_ui()
        self._apply_theme()

        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self):
        """Setup control bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Home button (leftmost)
        self.home_btn = QPushButton("⌂ Home")
        self.home_btn.setFixedSize(100, 40)
        self.home_btn.setObjectName("home_btn")
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        layout.addSpacing(40)

        # Portfolio selector
        layout.addWidget(QLabel("Portfolio:"))
        self.portfolio_combo = QComboBox()
        self.portfolio_combo.setMinimumWidth(200)
        self.portfolio_combo.currentTextChanged.connect(
            lambda name: self.portfolio_changed.emit(name) if name else None
        )
        layout.addWidget(self.portfolio_combo)

        # New portfolio button
        self.new_btn = QPushButton("New")
        self.new_btn.clicked.connect(self.new_portfolio_clicked.emit)
        layout.addWidget(self.new_btn)

        layout.addSpacing(20)

        # Save button
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_clicked.emit)
        layout.addWidget(self.save_btn)

    def set_view_mode(self, is_transaction_view: bool):
        """
        Show/hide buttons based on active view.

        Args:
            is_transaction_view: True for Transaction Log (show New/Save buttons),
                                False for Portfolio Holdings (hide editing buttons)
        """
        self.new_btn.setVisible(is_transaction_view)
        self.save_btn.setVisible(is_transaction_view)

    def update_portfolio_list(self, portfolios: List[str], current: str = None):
        """
        Update portfolio dropdown.

        Args:
            portfolios: List of portfolio names
            current: Currently selected portfolio name
        """
        self.portfolio_combo.blockSignals(True)
        self.portfolio_combo.clear()
        self.portfolio_combo.addItems(portfolios)
        if current and current in portfolios:
            self.portfolio_combo.setCurrentText(current)
        self.portfolio_combo.blockSignals(False)

    def get_current_portfolio(self) -> str:
        """
        Get currently selected portfolio name.

        Returns:
            Portfolio name or empty string
        """
        return self.portfolio_combo.currentText()

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Dark theme stylesheet."""
        return """
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 5px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #00d4ff;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #ffffff;
                margin-right: 5px;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #00d4ff;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
            QPushButton#home_btn {
                background-color: transparent;
                border: 1px solid transparent;
                font-weight: bold;
            }
            QPushButton#home_btn:hover {
                background-color: rgba(0, 212, 255, 0.15);
                border: 1px solid #00d4ff;
            }
            QPushButton#home_btn:pressed {
                background-color: #00d4ff;
                color: #000000;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
            }
            QComboBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #0066cc;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #000000;
                margin-right: 5px;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton#home_btn {
                background-color: transparent;
                border: 1px solid transparent;
                font-weight: bold;
            }
            QPushButton#home_btn:hover {
                background-color: rgba(0, 102, 204, 0.15);
                border: 1px solid #0066cc;
            }
            QPushButton#home_btn:pressed {
                background-color: #0066cc;
                color: #ffffff;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QWidget {
                background-color: #000814;
                color: #e8e8e8;
            }
            QLabel {
                color: #a8a8a8;
                font-size: 13px;
            }
            QComboBox {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 5px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #FF8000;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #e8e8e8;
                margin-right: 5px;
            }
            QPushButton {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1a2838;
                border-color: #FF8000;
            }
            QPushButton:pressed {
                background-color: #060a10;
            }
            QPushButton#home_btn {
                background-color: transparent;
                border: 1px solid transparent;
                font-weight: bold;
            }
            QPushButton#home_btn:hover {
                background-color: rgba(255, 128, 0, 0.15);
                border: 1px solid #FF8000;
            }
            QPushButton#home_btn:pressed {
                background-color: #FF8000;
                color: #000000;
            }
        """
