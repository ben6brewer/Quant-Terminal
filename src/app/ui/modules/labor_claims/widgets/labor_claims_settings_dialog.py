"""Labor Claims Settings Dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
)

from app.ui.widgets.common import ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService


class LaborClaimsSettingsDialog(ThemedDialog):
    """Settings dialog for the Labor Claims module."""

    def __init__(self, theme_manager, current_settings: dict, parent=None):
        self._current_settings = current_settings
        self.result = None
        super().__init__(theme_manager, "Claims Settings", parent, min_width=340)

    def _setup_content(self, layout):
        display_header = QLabel("Display")
        display_header.setObjectName("sectionHeader")
        layout.addWidget(display_header)
        layout.addSpacing(8)

        self.gridlines_cb = QCheckBox("Show Gridlines")
        self.gridlines_cb.setChecked(self._current_settings.get("show_gridlines", True))
        layout.addWidget(self.gridlines_cb)

        self.crosshair_cb = QCheckBox("Show Crosshair")
        self.crosshair_cb.setChecked(self._current_settings.get("show_crosshair", True))
        layout.addWidget(self.crosshair_cb)

        self.legend_cb = QCheckBox("Show Legend")
        self.legend_cb.setChecked(self._current_settings.get("show_legend", True))
        layout.addWidget(self.legend_cb)

        self.hover_tooltip_cb = QCheckBox("Show Hover Tooltip")
        self.hover_tooltip_cb.setChecked(self._current_settings.get("show_hover_tooltip", True))
        layout.addWidget(self.hover_tooltip_cb)

        layout.addSpacing(16)

        rec_header = QLabel("Recession Shading")
        rec_header.setObjectName("sectionHeader")
        layout.addWidget(rec_header)
        layout.addSpacing(8)

        self.recession_cb = QCheckBox("Show NBER Recession Shading")
        self.recession_cb.setChecked(self._current_settings.get("show_recession_shading", True))
        layout.addWidget(self.recession_cb)

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.setObjectName("defaultButton")
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)
        self._apply_extra_theme()

    def _save_settings(self):
        self.result = {
            "show_gridlines": self.gridlines_cb.isChecked(),
            "show_crosshair": self.crosshair_cb.isChecked(),
            "show_legend": self.legend_cb.isChecked(),
            "show_hover_tooltip": self.hover_tooltip_cb.isChecked(),
            "show_recession_shading": self.recession_cb.isChecked(),
        }
        self.accept()

    def get_settings(self) -> dict:
        return self.result

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
