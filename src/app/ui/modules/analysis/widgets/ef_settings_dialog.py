"""Efficient Frontier Settings Dialog - Gridlines, color scale, individual securities."""

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


EF_COLORSCALE_OPTIONS = [
    "Magma",
    "Viridis",
    "Plasma",
    "Inferno",
    "Cool-Warm",
]


class EFSettingsDialog(ThemedDialog):
    """Settings dialog for the Efficient Frontier module."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        current_settings: dict,
        parent=None,
    ):
        self.current_settings = current_settings
        super().__init__(theme_manager, "Efficient Frontier Settings", parent, min_width=400)
        self._apply_extra_theme()

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content - called by ThemedDialog."""
        header = QLabel("Display Settings")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # Show gridlines toggle
        self.gridlines_check = QCheckBox("Show Gridlines")
        self.gridlines_check.setFixedHeight(32)
        layout.addWidget(self.gridlines_check)

        layout.addSpacing(4)

        # Show individual securities toggle
        self.individuals_check = QCheckBox("Show Individual Securities")
        self.individuals_check.setFixedHeight(32)
        layout.addWidget(self.individuals_check)

        layout.addSpacing(8)

        # Color scale row
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        color_label = QLabel("Dot Color Scale:")
        color_label.setMinimumWidth(120)
        color_row.addWidget(color_label)

        self.colorscale_combo = NoScrollComboBox()
        for name in EF_COLORSCALE_OPTIONS:
            self.colorscale_combo.addItem(name)
        self.colorscale_combo.setFixedHeight(32)
        self.colorscale_combo.setMinimumWidth(180)
        color_row.addWidget(self.colorscale_combo)
        color_row.addStretch()
        layout.addLayout(color_row)

        layout.addSpacing(12)

        # Chart elements section
        elements_header = QLabel("Chart Elements")
        elements_header.setObjectName("sectionHeader")
        layout.addWidget(elements_header)

        self.frontier_check = QCheckBox("Efficient Frontier")
        self.frontier_check.setFixedHeight(32)
        layout.addWidget(self.frontier_check)

        layout.addSpacing(4)

        self.cml_check = QCheckBox("Capital Market Line")
        self.cml_check.setFixedHeight(32)
        layout.addWidget(self.cml_check)

        layout.addSpacing(4)

        self.max_sharpe_check = QCheckBox("Max Sharpe")
        self.max_sharpe_check.setFixedHeight(32)
        layout.addWidget(self.max_sharpe_check)

        layout.addSpacing(4)

        self.min_vol_check = QCheckBox("Min Volatility")
        self.min_vol_check.setFixedHeight(32)
        layout.addWidget(self.min_vol_check)

        layout.addSpacing(4)

        self.max_sortino_check = QCheckBox("Max Sortino")
        self.max_sortino_check.setFixedHeight(32)
        layout.addWidget(self.max_sortino_check)

        layout.addSpacing(4)

        self.indifference_check = QCheckBox("Indifference Curve")
        self.indifference_check.setFixedHeight(32)
        layout.addWidget(self.indifference_check)

        layout.addSpacing(4)

        self.leverage_check = QCheckBox("Allow Leverage")
        self.leverage_check.setFixedHeight(32)
        layout.addWidget(self.leverage_check)

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
            self.current_settings.get("ef_show_gridlines", True)
        )
        self.individuals_check.setChecked(
            self.current_settings.get("ef_show_individual_securities", True)
        )
        colorscale = self.current_settings.get("ef_colorscale", "Magma")
        idx = self.colorscale_combo.findText(colorscale)
        if idx >= 0:
            self.colorscale_combo.setCurrentIndex(idx)

        self.frontier_check.setChecked(
            self.current_settings.get("ef_show_frontier", True)
        )
        self.cml_check.setChecked(
            self.current_settings.get("ef_show_cml", True)
        )
        self.max_sharpe_check.setChecked(
            self.current_settings.get("ef_show_max_sharpe", True)
        )
        self.min_vol_check.setChecked(
            self.current_settings.get("ef_show_min_vol", True)
        )
        self.max_sortino_check.setChecked(
            self.current_settings.get("ef_show_max_sortino", True)
        )
        self.indifference_check.setChecked(
            self.current_settings.get("ef_show_indifference_curve", True)
        )
        self.leverage_check.setChecked(
            self.current_settings.get("ef_allow_leverage", True)
        )

    def _save_settings(self):
        """Save settings and close."""
        self.result = {
            "ef_show_gridlines": self.gridlines_check.isChecked(),
            "ef_colorscale": self.colorscale_combo.currentText(),
            "ef_show_individual_securities": self.individuals_check.isChecked(),
            "ef_show_frontier": self.frontier_check.isChecked(),
            "ef_show_cml": self.cml_check.isChecked(),
            "ef_show_max_sharpe": self.max_sharpe_check.isChecked(),
            "ef_show_min_vol": self.min_vol_check.isChecked(),
            "ef_show_max_sortino": self.max_sortino_check.isChecked(),
            "ef_show_indifference_curve": self.indifference_check.isChecked(),
            "ef_allow_leverage": self.leverage_check.isChecked(),
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
