"""OLS Settings Dialog - Display settings for OLS Regression module."""

from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QCheckBox,
)

from app.ui.widgets.common import ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService


class OLSSettingsDialog(ThemedDialog):
    """Settings dialog for the OLS Regression module."""

    def __init__(self, theme_manager, current_settings: dict, parent=None):
        self._current_settings = current_settings
        self.result = None
        super().__init__(theme_manager, "OLS Regression Settings", parent, min_width=400)

    def _setup_content(self, layout):
        # ── Display Options ──────────────────────────────────────────
        display_header = QLabel("Display Options")
        display_header.setObjectName("sectionHeader")
        layout.addWidget(display_header)

        layout.addSpacing(8)

        checkbox_grid = QGridLayout()
        checkbox_grid.setSpacing(8)

        self.gridlines_cb = QCheckBox("Show Gridlines")
        self.gridlines_cb.setChecked(self._current_settings.get("show_gridlines", True))
        checkbox_grid.addWidget(self.gridlines_cb, 0, 0)

        self.confidence_cb = QCheckBox("Show Confidence Bands")
        self.confidence_cb.setChecked(self._current_settings.get("show_confidence_bands", True))
        checkbox_grid.addWidget(self.confidence_cb, 1, 0)

        self.equation_cb = QCheckBox("Show Equation")
        self.equation_cb.setChecked(self._current_settings.get("show_equation", True))
        checkbox_grid.addWidget(self.equation_cb, 0, 1)

        self.stats_panel_cb = QCheckBox("Show Stats Panel")
        self.stats_panel_cb.setChecked(self._current_settings.get("show_stats_panel", True))
        checkbox_grid.addWidget(self.stats_panel_cb, 1, 1)

        layout.addLayout(checkbox_grid)

        layout.addStretch()

        # ── Buttons ──────────────────────────────────────────────────
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

    def _save_settings(self):
        self.result = {
            "show_gridlines": self.gridlines_cb.isChecked(),
            "show_confidence_bands": self.confidence_cb.isChecked(),
            "show_equation": self.equation_cb.isChecked(),
            "show_stats_panel": self.stats_panel_cb.isChecked(),
        }
        self.accept()

    def get_settings(self) -> dict:
        return self.result

    def _apply_theme(self):
        super()._apply_theme()
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
        additional_style = f"""
            QCheckBox {{ color: {c['text']}; spacing: 8px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
            QLabel#sectionHeader {{
                color: {c['text']};
                font-size: 14px;
                font-weight: 600;
                background: transparent;
                padding-bottom: 4px;
            }}
        """
        self.setStyleSheet(self.styleSheet() + additional_style)
