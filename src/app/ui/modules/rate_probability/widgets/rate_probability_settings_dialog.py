"""Rate Probability Settings Dialog - Toggle gridlines, table visibility."""

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
)

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService


class RateProbabilitySettingsDialog(ThemedDialog):
    """Settings dialog for the Rate Probability module."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        current_settings: dict,
        parent=None,
    ):
        self.current_settings = current_settings
        super().__init__(theme_manager, "Rate Probability Settings", parent, min_width=380)
        self._apply_extra_theme()

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content - called by ThemedDialog."""
        # Charts section
        charts_header = QLabel("Charts")
        charts_header.setObjectName("sectionHeader")
        layout.addWidget(charts_header)

        self.gridlines_check = QCheckBox("Show Gridlines")
        self.gridlines_check.setFixedHeight(32)
        layout.addWidget(self.gridlines_check)

        layout.addSpacing(12)

        # FedWatch section
        fedwatch_header = QLabel("FedWatch View")
        fedwatch_header.setObjectName("sectionHeader")
        layout.addWidget(fedwatch_header)

        self.prob_table_check = QCheckBox("Show Probability Table")
        self.prob_table_check.setFixedHeight(32)
        layout.addWidget(self.prob_table_check)

        layout.addSpacing(4)

        self.futures_table_check = QCheckBox("Show Futures Table")
        self.futures_table_check.setFixedHeight(32)
        layout.addWidget(self.futures_table_check)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.setDefault(True)
        self.save_btn.setObjectName("defaultButton")
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

        # Load current values
        self._load_settings()

    def _load_settings(self):
        """Populate widgets from current_settings."""
        self.gridlines_check.setChecked(
            self.current_settings.get("show_gridlines", True)
        )
        self.prob_table_check.setChecked(
            self.current_settings.get("show_probability_table", True)
        )
        self.futures_table_check.setChecked(
            self.current_settings.get("show_futures_table", True)
        )

    def _save_settings(self):
        """Save settings and close."""
        self.result = {
            "show_gridlines": self.gridlines_check.isChecked(),
            "show_probability_table": self.prob_table_check.isChecked(),
            "show_futures_table": self.futures_table_check.isChecked(),
        }
        self.accept()

    def get_settings(self) -> dict:
        """Return dict with updated keys."""
        return getattr(self, "result", None)

    def _apply_extra_theme(self):
        """Apply additional styling."""
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
        self.setStyleSheet(self.styleSheet() + f"""
            QLabel#sectionHeader {{
                color: {c['text']};
                font-size: 14px;
                font-weight: 600;
                background: transparent;
                padding-bottom: 4px;
            }}
            QCheckBox {{
                color: {c['text']};
                font-size: 13px;
                spacing: 8px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {c['border']};
                border-radius: 3px;
                background-color: {c['bg_header']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {c['accent']};
                border-color: {c['accent']};
            }}
        """)
