"""Custom Date Dialog - YYYY-MM-DD date range picker for custom lookback periods."""

from PySide6.QtWidgets import QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import QDate

from app.ui.widgets.common import ThemedDialog
from app.ui.widgets.common.date_input_widget import DateInputWidget
from app.services.theme_stylesheet_service import ThemeStylesheetService


class CustomDateDialog(ThemedDialog):
    """Dialog for selecting a custom date range with YYYY-MM-DD inputs."""

    def __init__(self, theme_manager, parent=None):
        self._date_range = None
        super().__init__(theme_manager, "Custom Date Range", parent, min_width=360)

    def _setup_content(self, layout):
        # Start date row
        start_row = QHBoxLayout()
        start_label = QLabel("Start Date:")
        start_label.setFixedWidth(80)
        start_label.setObjectName("field_label")
        self.start_input = DateInputWidget()
        self.start_input.setFixedHeight(36)
        start_row.addWidget(start_label)
        start_row.addWidget(self.start_input)
        layout.addLayout(start_row)

        layout.addSpacing(8)

        # End date row
        end_row = QHBoxLayout()
        end_label = QLabel("End Date:")
        end_label.setFixedWidth(80)
        end_label.setObjectName("field_label")
        self.end_input = DateInputWidget()
        self.end_input.setFixedHeight(36)
        self.end_input.setDate(QDate.currentDate())
        end_row.addWidget(end_label)
        end_row.addWidget(self.end_input)
        layout.addLayout(end_row)

        layout.addSpacing(4)

        # Error label (hidden by default)
        self.error_label = QLabel("")
        self.error_label.setObjectName("error_label")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        layout.addSpacing(12)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        btn_row.addSpacing(8)

        self.ok_btn = QPushButton("OK")
        self.ok_btn.setFixedHeight(34)
        self.ok_btn.setMinimumWidth(80)
        self.ok_btn.setObjectName("ok_btn")
        self.ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(self.ok_btn)

        layout.addLayout(btn_row)

        self._apply_extra_theme()

    def _on_ok(self):
        """Validate inputs and accept if valid."""
        start_text = self.start_input.text().strip()
        end_text = self.end_input.text().strip()

        if len(start_text.replace("-", "")) < 8:
            self._show_error("Please enter a complete start date (YYYY-MM-DD)")
            return

        if len(end_text.replace("-", "")) < 8:
            self._show_error("Please enter a complete end date (YYYY-MM-DD)")
            return

        # Parse directly from text (weekends and holidays are valid)
        start_date = QDate.fromString(start_text, "yyyy-MM-dd")
        end_date = QDate.fromString(end_text, "yyyy-MM-dd")

        if not start_date.isValid():
            self._show_error("Please enter a valid start date (YYYY-MM-DD)")
            return

        if not end_date.isValid():
            self._show_error("Please enter a valid end date (YYYY-MM-DD)")
            return

        if start_date >= end_date:
            self._show_error("Start date must be before end date")
            return

        if end_date > QDate.currentDate():
            self._show_error("End date cannot be in the future")
            return

        # Store as ISO strings for pandas compatibility
        self._date_range = (
            start_date.toString("yyyy-MM-dd"),
            end_date.toString("yyyy-MM-dd"),
        )
        self.accept()

    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()

    def get_date_range(self):
        """Return (start_iso, end_iso) tuple or None."""
        return self._date_range

    def _apply_extra_theme(self):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if self.theme_manager.current_theme == "dark":
            ok_hover = "#00bfe6"
        elif self.theme_manager.current_theme == "light":
            ok_hover = "#0055aa"
        else:
            ok_hover = "#e67300"

        self.setStyleSheet(self.styleSheet() + f"""
            QLabel#field_label {{
                color: {c['text']};
                font-size: 14px;
                background: transparent;
            }}
            QLabel#error_label {{
                color: #ff4444;
                font-size: 12px;
                background: transparent;
                padding: 2px 0px;
            }}
            QLineEdit {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 10px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
            QPushButton {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                border-color: {c['accent']};
            }}
            QPushButton#ok_btn {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                font-weight: bold;
                border: 1px solid {c['accent']};
            }}
            QPushButton#ok_btn:hover {{
                background-color: {ok_hover};
                border-color: {ok_hover};
            }}
        """)
