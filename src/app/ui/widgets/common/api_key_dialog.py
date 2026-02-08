"""API Key Dialog - FRED API key entry dialog (shared across modules)."""

from typing import Optional

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.themed_dialog import ThemedDialog


class APIKeyDialog(ThemedDialog):
    """Dialog for entering or updating the FRED API key."""

    def __init__(self, theme_manager: ThemeManager, parent=None, current_key: str = ""):
        self._api_key: Optional[str] = None
        self._current_key = current_key
        super().__init__(theme_manager, "FRED API Key", parent, min_width=450)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        desc = QLabel(
            "Enter your FRED API key to fetch Federal Reserve data.\n"
            "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
        )
        desc.setWordWrap(True)
        desc.setObjectName("description_label")
        layout.addWidget(desc)

        layout.addSpacing(10)

        # API key input row
        key_row = QHBoxLayout()
        key_row.setSpacing(10)

        key_label = QLabel("API Key:")
        key_label.setObjectName("field_label")
        key_row.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Enter your FRED API key")
        self.key_input.setFixedHeight(36)
        if self._current_key:
            self.key_input.setText(self._current_key)
        key_row.addWidget(self.key_input)

        # Show/Hide toggle
        self.toggle_btn = QPushButton("Show")
        self.toggle_btn.setFixedSize(60, 36)
        self.toggle_btn.clicked.connect(self._toggle_visibility)
        key_row.addWidget(self.toggle_btn)

        layout.addLayout(key_row)

        layout.addStretch()

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setFixedSize(100, 36)
        save_btn.setObjectName("defaultButton")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _toggle_visibility(self):
        """Toggle API key visibility."""
        if self.key_input.echoMode() == QLineEdit.Password:
            self.key_input.setEchoMode(QLineEdit.Normal)
            self.toggle_btn.setText("Hide")
        else:
            self.key_input.setEchoMode(QLineEdit.Password)
            self.toggle_btn.setText("Show")

    def _on_save(self):
        """Handle save button click."""
        key = self.key_input.text().strip()
        if key:
            self._api_key = key
            self.accept()

    def get_api_key(self) -> Optional[str]:
        """Get the entered API key (after dialog accepted)."""
        return self._api_key
