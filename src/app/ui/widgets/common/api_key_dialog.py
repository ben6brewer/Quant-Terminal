"""API Key Dialog - FRED API key entry dialog (shared across modules)."""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)
from PySide6.QtCore import Qt, QThread, Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.themed_dialog import ThemedDialog

logger = logging.getLogger(__name__)


class _ValidateKeyThread(QThread):
    """Background thread to validate a FRED API key."""

    success = Signal()
    failed = Signal(str)

    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._succeeded = False
        self._error_msg = None

    def run(self):
        try:
            from fredapi import Fred

            fred = Fred(api_key=self._api_key)
            fred.get_series_info("GNPCA")
            self._succeeded = True
        except Exception as exc:
            msg = str(exc)
            if "Bad Request" in msg or "400" in msg:
                self._error_msg = "Invalid API key. Please check and try again."
            else:
                self._error_msg = f"Validation failed: {msg}"


class APIKeyDialog(ThemedDialog):
    """Dialog for entering or updating the FRED API key."""

    def __init__(self, theme_manager: ThemeManager, parent=None, current_key: str = ""):
        self._api_key: Optional[str] = None
        self._current_key = current_key
        self._validate_thread: Optional[_ValidateKeyThread] = None
        super().__init__(theme_manager, "FRED API Key", parent, min_width=450)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        desc = QLabel(
            'Enter your FRED API key to fetch Federal Reserve data.<br>'
            'Get a free key at <a href="https://fred.stlouisfed.org/docs/api/api_key.html">'
            'fred.stlouisfed.org/docs/api/api_key.html</a>'
        )
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        desc.setOpenExternalLinks(True)
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

        # Error label (hidden by default)
        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #ff4444; font-size: 12px;")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        layout.addStretch()

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedSize(100, 36)
        self._save_btn.setObjectName("defaultButton")
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

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
        """Handle save button click — validate key before accepting."""
        key = self.key_input.text().strip()
        if not key:
            return

        # Disable UI while validating
        self._save_btn.setEnabled(False)
        self._save_btn.setText("Validating...")
        self._error_label.hide()
        self.key_input.setEnabled(False)

        self._pending_key = key
        self._validate_thread = _ValidateKeyThread(key, self)
        self._validate_thread.finished.connect(self._on_validate_thread_done, Qt.QueuedConnection)
        self._validate_thread.start()

    def _on_validate_thread_done(self):
        """Dispatch validation result on main thread."""
        thread = self._validate_thread
        if thread is None:
            return
        key = self._pending_key
        if thread._succeeded:
            self._on_validation_done(key)
        elif thread._error_msg:
            self._on_validation_failed(thread._error_msg)
        else:
            self._on_validation_failed("Validation failed (unknown error)")

    def _on_validation_done(self, key: str):
        """Key validated successfully — accept dialog."""
        self._api_key = key
        self.accept()

    def _on_validation_failed(self, message: str):
        """Key validation failed — show error and re-enable UI."""
        logger.warning("FRED API key validation failed: %s", message)
        self._error_label.setText(message)
        self._error_label.show()
        self._save_btn.setEnabled(True)
        self._save_btn.setText("Save")
        self.key_input.setEnabled(True)
        self.key_input.setFocus()

    def get_api_key(self) -> Optional[str]:
        """Get the entered API key (after dialog accepted)."""
        return self._api_key
