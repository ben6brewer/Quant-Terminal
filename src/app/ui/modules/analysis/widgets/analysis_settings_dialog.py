"""Analysis Settings Dialog - Decimal places and color scale for matrix modules."""

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import ThemedDialog, NoScrollComboBox
from app.services.theme_stylesheet_service import ThemeStylesheetService


COLORSCALE_OPTIONS = [
    "Green-Yellow-Red",
    "Blue-White-Red",
    "Purple-White-Orange",
    "Viridis",
    "Plasma",
]

DECIMAL_OPTIONS = [
    ("0", 0),
    ("1", 1),
    ("2", 2),
    ("3", 3),
    ("4", 4),
    ("5", 5),
    ("6", 6),
]


class AnalysisSettingsDialog(ThemedDialog):
    """Settings dialog for correlation/covariance matrix display options."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        current_settings: dict,
        mode: str = "correlation",
        parent=None,
    ):
        self.current_settings = current_settings
        self._mode = mode
        self._decimals_key = "corr_decimals" if mode == "correlation" else "cov_decimals"

        title = (
            "Correlation Matrix Settings"
            if mode == "correlation"
            else "Covariance Matrix Settings"
        )

        super().__init__(theme_manager, title, parent, min_width=400)
        self._apply_extra_theme()

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content - called by ThemedDialog."""
        # Section header
        header = QLabel("Display Settings")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

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
        default_decimals = 3 if self._mode == "correlation" else 4
        decimals = self.current_settings.get(self._decimals_key, default_decimals)
        for i in range(self.decimals_combo.count()):
            if self.decimals_combo.itemData(i) == decimals:
                self.decimals_combo.setCurrentIndex(i)
                break

        colorscale = self.current_settings.get("matrix_colorscale", "Green-Yellow-Red")
        idx = self.colorscale_combo.findText(colorscale)
        if idx >= 0:
            self.colorscale_combo.setCurrentIndex(idx)

    def _save_settings(self):
        """Save settings and close."""
        self.result = {
            self._decimals_key: self.decimals_combo.currentData(),
            "matrix_colorscale": self.colorscale_combo.currentText(),
        }
        self.accept()

    def get_settings(self) -> dict:
        """Return dict with updated keys."""
        return getattr(self, "result", None)

    def _apply_extra_theme(self):
        """Apply additional styling for section header."""
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
        self.setStyleSheet(self.styleSheet() + f"""
            QLabel#sectionHeader {{
                color: {c['text']};
                font-size: 14px;
                font-weight: 600;
                background: transparent;
                padding-bottom: 4px;
            }}
        """)
