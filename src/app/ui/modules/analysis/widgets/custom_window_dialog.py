"""Custom Window Dialog - Enter rolling window size in decimal years."""

from PySide6.QtWidgets import QLabel, QHBoxLayout, QPushButton, QVBoxLayout
from PySide6.QtCore import Qt

from app.ui.widgets.common import ThemedDialog, ValidatedNumericLineEdit
from app.services.theme_stylesheet_service import ThemeStylesheetService


class CustomWindowDialog(ThemedDialog):
    """Dialog for entering a custom rolling window in decimal years."""

    def __init__(self, theme_manager, parent=None):
        self._years = None
        super().__init__(theme_manager, "Custom Rolling Window", parent, min_width=340)

    def _setup_content(self, layout):
        # Years input row
        input_row = QHBoxLayout()
        input_label = QLabel("Years:")
        input_label.setFixedWidth(60)
        input_label.setObjectName("field_label")
        self.years_input = ValidatedNumericLineEdit(
            min_value=0.01, max_value=50.0, decimals=2
        )
        self.years_input.setPlaceholderText("e.g. 0.5")
        self.years_input.setFixedHeight(36)
        input_row.addWidget(input_label)
        input_row.addWidget(self.years_input)
        layout.addLayout(input_row)

        layout.addSpacing(4)

        # Info text
        info_label = QLabel("0.5 = ~126 days, 1.0 = ~252 days")
        info_label.setObjectName("descriptionLabel")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

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
        text = self.years_input.text().strip()
        if not text:
            self._show_error("Please enter a value")
            return

        try:
            years = float(text)
        except ValueError:
            self._show_error("Please enter a valid number")
            return

        if years <= 0:
            self._show_error("Value must be greater than 0")
            return

        trading_days = int(round(years * 252))
        if trading_days < 2:
            self._show_error("Window must be at least 2 trading days")
            return

        self._years = years
        self.accept()

    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()

    def get_years(self) -> float:
        """Return the entered years value, or None."""
        return self._years

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
