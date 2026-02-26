"""Custom Start Date Dialog - Single date picker for custom CPI lookback."""

from PySide6.QtWidgets import QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import QDate

from app.ui.widgets.common import ThemedDialog
from app.ui.widgets.common.date_input_widget import DateInputWidget
from app.services.theme_stylesheet_service import ThemeStylesheetService


class CustomStartDateDialog(ThemedDialog):
    """Dialog for selecting a custom start date (end date is always today)."""

    def __init__(self, theme_manager, parent=None):
        self._start_date = None
        super().__init__(theme_manager, "Custom Start Date", parent, min_width=340)

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
        """Validate input and accept if valid."""
        start_text = self.start_input.text().strip()

        if len(start_text.replace("-", "")) < 8:
            self._show_error("Please enter a complete date (YYYY-MM-DD)")
            return

        start_date = QDate.fromString(start_text, "yyyy-MM-dd")

        if not start_date.isValid():
            self._show_error("Please enter a valid date (YYYY-MM-DD)")
            return

        if start_date > QDate.currentDate():
            self._show_error("Start date cannot be in the future")
            return

        if start_date.year() < 1950:
            self._show_error("Start date cannot be before 1950")
            return

        self._start_date = start_date.toString("yyyy-MM-dd")
        self.accept()

    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()

    def get_start_date(self) -> str:
        """Return ISO date string or None."""
        return self._start_date

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
