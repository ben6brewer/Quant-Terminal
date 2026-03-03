"""JOLTS Settings Dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QCheckBox,
)

from app.ui.widgets.common import ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService


JOLTS_DISPLAY_NAMES = {
    "Job Openings": "Job Openings",
    "Hires": "Hires",
    "Quits": "Quits",
    "Layoffs": "Layoffs & Discharges",
}


class JoltsSettingsDialog(ThemedDialog):
    """Settings dialog for the JOLTS module."""

    def __init__(self, theme_manager, current_settings: dict, parent=None):
        self._current_settings = current_settings
        self.result = None
        super().__init__(theme_manager, "JOLTS Settings", parent, min_width=380)

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

        layout.addSpacing(16)

        jolts_header = QLabel("Visible JOLTS Series")
        jolts_header.setObjectName("sectionHeader")
        layout.addWidget(jolts_header)
        layout.addSpacing(8)

        active_jolts = set(
            self._current_settings.get("jolts_series", ["Job Openings", "Hires", "Quits", "Layoffs"])
        )
        self._jolts_checkboxes = {}
        jolts_grid = QGridLayout()
        jolts_grid.setSpacing(6)
        for i, (key, display) in enumerate(JOLTS_DISPLAY_NAMES.items()):
            cb = QCheckBox(display)
            cb.setChecked(key in active_jolts)
            row, col = divmod(i, 2)
            jolts_grid.addWidget(cb, row, col)
            self._jolts_checkboxes[key] = cb
        layout.addLayout(jolts_grid)
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
        jolts_series = [key for key, cb in self._jolts_checkboxes.items() if cb.isChecked()]
        self.result = {
            "show_gridlines": self.gridlines_cb.isChecked(),
            "show_crosshair": self.crosshair_cb.isChecked(),
            "show_legend": self.legend_cb.isChecked(),
            "show_hover_tooltip": self.hover_tooltip_cb.isChecked(),
            "show_recession_shading": self.recession_cb.isChecked(),
            "jolts_series": jolts_series,
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
