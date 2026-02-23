"""Monthly Returns Controls Widget - Top Control Bar."""

from typing import List

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import LazyThemeMixin, PortfolioTickerComboBox


class MonthlyReturnsControls(LazyThemeMixin, QWidget):
    """Control bar for Monthly Returns module: Home button + Portfolio/Ticker selector."""

    home_clicked = Signal()
    portfolio_changed = Signal(str)
    settings_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Home button (leftmost)
        self.home_btn = QPushButton("Home")
        self.home_btn.setMinimumWidth(70)
        self.home_btn.setMaximumWidth(100)
        self.home_btn.setFixedHeight(40)
        self.home_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.home_btn.setObjectName("home_btn")
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        layout.addStretch(1)

        # Portfolio/Ticker selector
        self.portfolio_label = QLabel("Portfolio:")
        self.portfolio_label.setObjectName("control_label")
        layout.addWidget(self.portfolio_label)
        self.portfolio_combo = PortfolioTickerComboBox()
        self.portfolio_combo.setMinimumWidth(140)
        self.portfolio_combo.setMaximumWidth(250)
        self.portfolio_combo.setFixedHeight(40)
        self.portfolio_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.portfolio_combo.value_changed.connect(self.portfolio_changed.emit)
        layout.addWidget(self.portfolio_combo)

        layout.addStretch(1)

        # Settings button (right-aligned)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setMinimumWidth(70)
        self.settings_btn.setMaximumWidth(100)
        self.settings_btn.setFixedHeight(40)
        self.settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def update_portfolio_list(self, portfolios: List[str], current: str = None):
        self.portfolio_combo.set_portfolios(portfolios, current)

    def set_ticker_text(self, ticker: str):
        """Set the combo box text to a ticker symbol."""
        self.portfolio_combo.lineEdit().setText(ticker)

    def _apply_theme(self):
        theme = self.theme_manager.current_theme
        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()
        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        return """
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
            }
            QLabel#control_label {
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QComboBox:hover {
                border-color: #00d4ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #ffffff;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
                font-size: 14px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:alternate {
                background-color: #252525;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #00d4ff;
                color: #000000;
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
        """

    def _get_light_stylesheet(self) -> str:
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
            }
            QLabel#control_label {
                color: #000000;
                font-size: 14px;
                font-weight: 500;
            }
            QComboBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QComboBox:hover {
                border-color: #0066cc;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #000000;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #f5f5f5;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
                font-size: 14px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:alternate {
                background-color: #e8e8e8;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #0066cc;
                color: #ffffff;
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
        """

    def _get_bloomberg_stylesheet(self) -> str:
        return """
            QWidget {
                background-color: #000814;
                color: #e8e8e8;
            }
            QLabel {
                color: #a8a8a8;
                font-size: 13px;
            }
            QLabel#control_label {
                color: #e8e8e8;
                font-size: 14px;
                font-weight: 500;
            }
            QComboBox {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QComboBox:hover {
                border-color: #FF8000;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #e8e8e8;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #0d1420;
                color: #e8e8e8;
                selection-background-color: #FF8000;
                selection-color: #000000;
                font-size: 14px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:alternate {
                background-color: #0a1018;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #FF8000;
                color: #000000;
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
        """
