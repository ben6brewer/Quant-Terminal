from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.themed_dialog import ThemedDialog


class CustomMessageBox(ThemedDialog):
    """
    Custom message box with themed title bar.
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
        self._text = text
        self._icon = icon
        self._buttons = buttons
        self._result = None
        super().__init__(theme_manager, title, parent, min_width=400)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup message text and buttons."""
        layout.setSpacing(20)

        # Message text
        message_label = QLabel(self._text)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        message_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(message_label)

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

        layout.addLayout(button_layout)

    def _on_button_clicked(self, button: int):
        """Handle button click."""
        self._result = button
        self.accept()

    def result_button(self) -> int:
        """Get which button was clicked."""
        return self._result if self._result is not None else self.Cancel

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
