"""Monthly Returns Settings Dialog - YTD, gradient, color scale, decimals."""

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
)

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import ThemedDialog, NoScrollComboBox
from app.services.theme_stylesheet_service import ThemeStylesheetService


COLORSCALE_OPTIONS = [
    "Red-Green",
    "Magma",
    "Viridis",
    "Plasma",
    "Inferno",
    "Cool-Warm",
]

DECIMAL_OPTIONS = [
    ("0", 0),
    ("1", 1),
    ("2", 2),
    ("3", 3),
    ("4", 4),
]


class MonthlyReturnsSettingsDialog(ThemedDialog):
    """Settings dialog for the Monthly Returns module."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        current_settings: dict,
        parent=None,
    ):
        self.current_settings = current_settings
        super().__init__(theme_manager, "Monthly Returns Settings", parent, min_width=400)
        self._apply_extra_theme()

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content - called by ThemedDialog."""
        header = QLabel("Display Settings")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # Show YTD column toggle
        self.ytd_check = QCheckBox("Show YTD Column")
        self.ytd_check.setFixedHeight(32)
        layout.addWidget(self.ytd_check)

        layout.addSpacing(4)

        # Gradient colors toggle
        self.gradient_check = QCheckBox("Gradient Colors")
        self.gradient_check.setFixedHeight(32)
        layout.addWidget(self.gradient_check)

        layout.addSpacing(8)

        # Color scale row
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        color_label = QLabel("Color Scale:")
        color_label.setMinimumWidth(120)
        color_row.addWidget(color_label)

        self.colorscale_combo = NoScrollComboBox()
        for name in COLORSCALE_OPTIONS:
            self.colorscale_combo.addItem(name)
        self.colorscale_combo.setFixedHeight(32)
        self.colorscale_combo.setMinimumWidth(180)
        color_row.addWidget(self.colorscale_combo)
        color_row.addStretch()
        layout.addLayout(color_row)

        layout.addSpacing(8)

        # Decimal places row
        decimals_row = QHBoxLayout()
        decimals_row.setSpacing(8)
        decimals_label = QLabel("Decimal Places:")
        decimals_label.setMinimumWidth(120)
        decimals_row.addWidget(decimals_label)

        self.decimals_combo = NoScrollComboBox()
        for label, val in DECIMAL_OPTIONS:
            self.decimals_combo.addItem(label, val)
        self.decimals_combo.setFixedHeight(32)
        self.decimals_combo.setMinimumWidth(140)
        decimals_row.addWidget(self.decimals_combo)
        decimals_row.addStretch()
        layout.addLayout(decimals_row)

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
        self.ytd_check.setChecked(self.current_settings.get("show_ytd", True))
        self.gradient_check.setChecked(self.current_settings.get("use_gradient", True))

        colorscale = self.current_settings.get("colorscale", "Magma")
        idx = self.colorscale_combo.findText(colorscale)
        if idx >= 0:
            self.colorscale_combo.setCurrentIndex(idx)

        decimals = self.current_settings.get("decimals", 2)
        for i in range(self.decimals_combo.count()):
            if self.decimals_combo.itemData(i) == decimals:
                self.decimals_combo.setCurrentIndex(i)
                break

    def _save_settings(self):
        """Save settings and close."""
        self.result = {
            "show_ytd": self.ytd_check.isChecked(),
            "use_gradient": self.gradient_check.isChecked(),
            "colorscale": self.colorscale_combo.currentText(),
            "decimals": self.decimals_combo.currentData(),
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
