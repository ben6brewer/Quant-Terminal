"""CPI Settings Dialog - Configure display and breakdown settings."""

from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QCheckBox,
)

from app.ui.widgets.common import ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService


class CpiSettingsDialog(ThemedDialog):
    """Settings dialog for the CPI module."""

    def __init__(self, theme_manager, current_settings: dict, parent=None):
        self._current_settings = current_settings
        self.result = None
        super().__init__(theme_manager, "CPI Settings", parent, min_width=420)

    def _setup_content(self, layout):
        # -- Chart View -------------------------------------------------------
        view_header = QLabel("Chart View")
        view_header.setObjectName("sectionHeader")
        layout.addWidget(view_header)

        layout.addSpacing(8)

        self.show_breakdown_cb = QCheckBox("Show Component Breakdown")
        self.show_breakdown_cb.setChecked(self._current_settings.get("show_breakdown", True))
        layout.addWidget(self.show_breakdown_cb)

        layout.addSpacing(16)

        # -- Display ----------------------------------------------------------
        display_header = QLabel("Display")
        display_header.setObjectName("sectionHeader")
        layout.addWidget(display_header)

        layout.addSpacing(8)

        checkbox_grid = QGridLayout()
        checkbox_grid.setSpacing(8)

        self.gridlines_cb = QCheckBox("Show Gridlines")
        self.gridlines_cb.setChecked(self._current_settings.get("show_gridlines", True))
        checkbox_grid.addWidget(self.gridlines_cb, 0, 0)

        self.value_label_cb = QCheckBox("Show Value Label")
        self.value_label_cb.setChecked(self._current_settings.get("show_value_label", True))
        checkbox_grid.addWidget(self.value_label_cb, 0, 1)

        self.ref_lines_cb = QCheckBox("Show Reference Lines")
        self.ref_lines_cb.setChecked(self._current_settings.get("show_reference_lines", True))
        checkbox_grid.addWidget(self.ref_lines_cb, 1, 0)

        self.date_label_cb = QCheckBox("Show Date Label")
        self.date_label_cb.setChecked(self._current_settings.get("show_date_label", True))
        checkbox_grid.addWidget(self.date_label_cb, 1, 1)

        self.crosshair_cb = QCheckBox("Show Crosshair")
        self.crosshair_cb.setChecked(self._current_settings.get("show_crosshair", True))
        checkbox_grid.addWidget(self.crosshair_cb, 2, 0)

        layout.addLayout(checkbox_grid)

        layout.addSpacing(16)

        # -- Breakdown --------------------------------------------------------
        breakdown_header = QLabel("Breakdown")
        breakdown_header.setObjectName("sectionHeader")
        layout.addWidget(breakdown_header)

        layout.addSpacing(8)

        self.headline_overlay_cb = QCheckBox("Show Headline Overlay")
        self.headline_overlay_cb.setChecked(self._current_settings.get("show_headline_overlay", True))
        layout.addWidget(self.headline_overlay_cb)

        layout.addSpacing(4)

        self.legend_cb = QCheckBox("Show Legend")
        self.legend_cb.setChecked(self._current_settings.get("show_legend", True))
        layout.addWidget(self.legend_cb)

        layout.addSpacing(4)

        self.hover_tooltip_cb = QCheckBox("Show Hover Tooltip")
        self.hover_tooltip_cb.setChecked(self._current_settings.get("show_hover_tooltip", True))
        layout.addWidget(self.hover_tooltip_cb)

        layout.addStretch()

        # -- Buttons ----------------------------------------------------------
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
            "show_breakdown": self.show_breakdown_cb.isChecked(),
            "show_gridlines": self.gridlines_cb.isChecked(),
            "show_reference_lines": self.ref_lines_cb.isChecked(),
            "show_crosshair": self.crosshair_cb.isChecked(),
            "show_value_label": self.value_label_cb.isChecked(),
            "show_date_label": self.date_label_cb.isChecked(),
            "show_headline_overlay": self.headline_overlay_cb.isChecked(),
            "show_legend": self.legend_cb.isChecked(),
            "show_hover_tooltip": self.hover_tooltip_cb.isChecked(),
        }
        self.accept()

    def get_settings(self) -> dict:
        return self.result

    def _apply_theme(self):
        super()._apply_theme()
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
