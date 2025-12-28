from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent

from app.core.theme_manager import ThemeManager


class CustomMessageBox(QDialog):
    """
    Custom message box with custom title bar matching the application theme.
    Replaces QMessageBox for consistent styling across all dialogs.
    """

    # Button roles
    Yes = 0x00004000
    No = 0x00010000
    Ok = 0x00000400
    Cancel = 0x00400000

    # Icon types
    NoIcon = 0
    Information = 1
    Warning = 2
    Critical = 3
    Question = 4

    def __init__(
        self,
        theme_manager: ThemeManager,
        parent=None,
        title: str = "",
        text: str = "",
        icon: int = NoIcon,
        buttons: int = Ok,
    ):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(400)

        # Remove native title bar
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        self.theme_manager = theme_manager
        self._title = title
        self._text = text
        self._icon = icon
        self._buttons = buttons
        self._result = None

        # For window dragging
        self._drag_pos = QPoint()

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Setup dialog with custom title bar."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Custom title bar
        self.title_bar = self._create_title_bar(self._title)
        layout.addWidget(self.title_bar)

        # Content container
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        # Message text
        message_label = QLabel(self._text)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        message_label.setStyleSheet("font-size: 13px;")
        content_layout.addWidget(message_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        if self._buttons & self.Yes:
            yes_btn = QPushButton("Yes")
            yes_btn.setMinimumWidth(80)
            yes_btn.clicked.connect(lambda: self._on_button_clicked(self.Yes))
            button_layout.addWidget(yes_btn)

        if self._buttons & self.No:
            no_btn = QPushButton("No")
            no_btn.setMinimumWidth(80)
            no_btn.clicked.connect(lambda: self._on_button_clicked(self.No))
            button_layout.addWidget(no_btn)

        if self._buttons & self.Ok:
            ok_btn = QPushButton("OK")
            ok_btn.setObjectName("defaultButton")
            ok_btn.setMinimumWidth(80)
            ok_btn.setDefault(True)
            ok_btn.clicked.connect(lambda: self._on_button_clicked(self.Ok))
            button_layout.addWidget(ok_btn)

        if self._buttons & self.Cancel:
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setMinimumWidth(80)
            cancel_btn.clicked.connect(lambda: self._on_button_clicked(self.Cancel))
            button_layout.addWidget(cancel_btn)

        content_layout.addLayout(button_layout)

        # Add content to main layout
        layout.addWidget(content_widget)

    def _create_title_bar(self, title: str) -> QWidget:
        """Create custom title bar with close button."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        bar_layout = QHBoxLayout(title_bar)
        bar_layout.setContentsMargins(10, 0, 0, 0)
        bar_layout.setSpacing(5)

        # Dialog title
        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        bar_layout.addWidget(title_label)

        bar_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBarCloseButton")
        close_btn.setFixedSize(40, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        bar_layout.addWidget(close_btn)

        # Enable dragging from title bar
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        return title_bar

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        """Handle mouse press on title bar for dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
        """Handle mouse move on title bar for dragging."""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _on_button_clicked(self, button: int):
        """Handle button click."""
        self._result = button
        self.accept()

    def result_button(self) -> int:
        """Get which button was clicked."""
        return self._result if self._result is not None else self.Cancel

    def _apply_theme(self):
        """Apply the current theme to the dialog."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Get dark theme stylesheet."""
        return """
            QDialog {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            #titleBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
            }
            #titleLabel {
                background-color: transparent;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
                background-color: transparent;
            }
            QPushButton {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #00d4ff;
                background-color: #2d2d2d;
            }
            QPushButton:pressed {
                background-color: #00d4ff;
                color: #000000;
            }
            QPushButton#defaultButton {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
            }
            QPushButton#defaultButton:hover {
                background-color: #00c4ef;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Get light theme stylesheet."""
        return """
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            #titleBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #cccccc;
            }
            #titleLabel {
                background-color: transparent;
                color: #000000;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(0, 0, 0, 0.08);
                color: #000000;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
                background-color: transparent;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #0066cc;
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                background-color: #0066cc;
                color: #ffffff;
            }
            QPushButton#defaultButton {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
            }
            QPushButton#defaultButton:hover {
                background-color: #0052a3;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Get Bloomberg theme stylesheet."""
        return """
            QDialog {
                background-color: #0d1420;
                color: #e8e8e8;
            }
            #titleBar {
                background-color: #0d1420;
                border-bottom: 1px solid #1a2332;
            }
            #titleLabel {
                background-color: transparent;
                color: #e8e8e8;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #e8e8e8;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 13px;
                background-color: transparent;
            }
            QPushButton {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #FF8000;
                background-color: rgba(255, 128, 0, 0.1);
            }
            QPushButton:pressed {
                background-color: #FF8000;
                color: #000000;
            }
            QPushButton#defaultButton {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
            }
            QPushButton#defaultButton:hover {
                background-color: #FF9520;
            }
        """

    @staticmethod
    def information(theme_manager: ThemeManager, parent, title: str, text: str):
        """Show an information dialog."""
        dialog = CustomMessageBox(
            theme_manager, parent, title, text, CustomMessageBox.Information, CustomMessageBox.Ok
        )
        dialog.exec()

    @staticmethod
    def warning(theme_manager: ThemeManager, parent, title: str, text: str):
        """Show a warning dialog."""
        dialog = CustomMessageBox(
            theme_manager, parent, title, text, CustomMessageBox.Warning, CustomMessageBox.Ok
        )
        dialog.exec()

    @staticmethod
    def critical(theme_manager: ThemeManager, parent, title: str, text: str):
        """Show a critical error dialog."""
        dialog = CustomMessageBox(
            theme_manager, parent, title, text, CustomMessageBox.Critical, CustomMessageBox.Ok
        )
        dialog.exec()

    @staticmethod
    def question(
        theme_manager: ThemeManager,
        parent,
        title: str,
        text: str,
        buttons: int = None,
        default_button: int = None,
    ) -> int:
        """Show a question dialog and return which button was clicked."""
        if buttons is None:
            buttons = CustomMessageBox.Yes | CustomMessageBox.No

        dialog = CustomMessageBox(
            theme_manager, parent, title, text, CustomMessageBox.Question, buttons
        )
        dialog.exec()
        return dialog.result_button()
