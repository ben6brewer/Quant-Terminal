"""Asset Class Returns Settings Dialog - Decimal places setting."""

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QCheckBox
from PySide6.QtGui import QDoubleValidator

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import ThemedDialog, NoScrollComboBox
from app.services.theme_stylesheet_service import ThemeStylesheetService

LABEL_OPTIONS = [
    ("Asset Class", "label"),
    ("Ticker", "ticker"),
]

DECIMAL_OPTIONS = [
    ("0", 0),
    ("1", 1),
    ("2", 2),
    ("3", 3),
    ("4", 4),
]


class AssetClassReturnsSettingsDialog(ThemedDialog):
    """Settings dialog for the Asset Class Returns module."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        current_settings: dict,
        parent=None,
    ):
        self.current_settings = current_settings
        super().__init__(theme_manager, "Asset Class Returns Settings", parent, min_width=400)
        self._apply_extra_theme()

    def _setup_content(self, layout: QVBoxLayout):
        header = QLabel("Display Settings")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        layout.addSpacing(8)

        # Label mode row
        label_row = QHBoxLayout()
        label_row.setSpacing(8)
        label_label = QLabel("Label:")
        label_label.setMinimumWidth(120)
        label_row.addWidget(label_label)

        self.label_combo = NoScrollComboBox()
        for display, val in LABEL_OPTIONS:
            self.label_combo.addItem(display, val)
        self.label_combo.setFixedHeight(32)
        self.label_combo.setMinimumWidth(140)
        label_row.addWidget(self.label_combo)
        label_row.addStretch()
        layout.addLayout(label_row)

        layout.addSpacing(4)

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

        layout.addSpacing(4)

        # CAGR lookback row
        cagr_row = QHBoxLayout()
        cagr_row.setSpacing(8)
        cagr_label = QLabel("CAGR Lookback (yrs):")
        cagr_label.setMinimumWidth(120)
        cagr_row.addWidget(cagr_label)

        self.cagr_input = QLineEdit()
        self.cagr_input.setPlaceholderText("Max")
        self.cagr_input.setValidator(QDoubleValidator(0.1, 100.0, 2))
        self.cagr_input.setFixedHeight(32)
        self.cagr_input.setMinimumWidth(140)
        cagr_row.addWidget(self.cagr_input)
        cagr_row.addStretch()
        layout.addLayout(cagr_row)

        layout.addSpacing(4)

        # Show CAGR column row
        show_cagr_row = QHBoxLayout()
        show_cagr_row.setSpacing(8)
        show_cagr_label = QLabel("Show CAGR Column:")
        show_cagr_label.setMinimumWidth(120)
        show_cagr_row.addWidget(show_cagr_label)

        self.show_cagr_check = QCheckBox()
        show_cagr_row.addWidget(self.show_cagr_check)
        show_cagr_row.addStretch()
        layout.addLayout(show_cagr_row)

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

        self._load_settings()

    def _load_settings(self):
        label_mode = self.current_settings.get("label_mode", "label")
        for i in range(self.label_combo.count()):
            if self.label_combo.itemData(i) == label_mode:
                self.label_combo.setCurrentIndex(i)
                break

        decimals = self.current_settings.get("decimals", 1)
        for i in range(self.decimals_combo.count()):
            if self.decimals_combo.itemData(i) == decimals:
                self.decimals_combo.setCurrentIndex(i)
                break

        cagr_years = self.current_settings.get("cagr_years")
        if cagr_years is not None:
            s = f"{cagr_years:.2f}".rstrip("0").rstrip(".")
            self.cagr_input.setText(s)

        self.show_cagr_check.setChecked(self.current_settings.get("show_cagr", True))

    def _save_settings(self):
        cagr_text = self.cagr_input.text().strip()
        cagr_years = None
        if cagr_text:
            try:
                cagr_years = float(cagr_text)
            except ValueError:
                pass

        self.result = {
            "label_mode": self.label_combo.currentData(),
            "decimals": self.decimals_combo.currentData(),
            "cagr_years": cagr_years,
            "show_cagr": self.show_cagr_check.isChecked(),
        }
        self.accept()

    def get_settings(self) -> dict:
        return getattr(self, "result", None)

    def _apply_extra_theme(self):
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
