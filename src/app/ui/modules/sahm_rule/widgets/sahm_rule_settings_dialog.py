"""Sahm Rule Settings Dialog - Configure threshold and display settings."""

from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QGridLayout,
)

from app.ui.widgets.common import ThemedDialog
from app.ui.widgets.common.validated_numeric_line_edit import ValidatedNumericLineEdit
from app.services.theme_stylesheet_service import ThemeStylesheetService


class SahmRuleSettingsDialog(ThemedDialog):
    """Settings dialog for the Sahm Rule module."""

    def __init__(self, theme_manager, current_settings: dict, parent=None):
        self._current_settings = current_settings
        self.result = None
        super().__init__(theme_manager, "Sahm Rule Settings", parent, min_width=420)

    def _setup_content(self, layout):
        # -- Threshold ----------------------------------------------------
        threshold_header = QLabel("Threshold")
        threshold_header.setObjectName("sectionHeader")
        layout.addWidget(threshold_header)

        layout.addSpacing(8)

        self.show_threshold_cb = QCheckBox("Show threshold line")
        self.show_threshold_cb.setChecked(self._current_settings.get("show_threshold", True))
        self.show_threshold_cb.toggled.connect(self._on_threshold_toggled)
        layout.addWidget(self.show_threshold_cb)

        layout.addSpacing(4)

        value_row = QHBoxLayout()
        value_label = QLabel("Threshold value:")
        value_row.addWidget(value_label)

        self.threshold_input = ValidatedNumericLineEdit(
            min_value=0.0, max_value=10.0, decimals=2
        )
        self.threshold_input.setFixedWidth(80)
        self.threshold_input.setValue(self._current_settings.get("threshold_value", 0.50))
        value_row.addWidget(self.threshold_input)
        value_row.addStretch()
        layout.addLayout(value_row)

        self._on_threshold_toggled(self.show_threshold_cb.isChecked())

        layout.addSpacing(16)

        # -- Display ------------------------------------------------------
        display_header = QLabel("Display")
        display_header.setObjectName("sectionHeader")
        layout.addWidget(display_header)

        layout.addSpacing(8)

        checkbox_grid = QGridLayout()
        checkbox_grid.setSpacing(8)

        self.recession_cb = QCheckBox("Show recession shading")
        self.recession_cb.setChecked(self._current_settings.get("show_recession_bands", True))
        checkbox_grid.addWidget(self.recession_cb, 0, 0)

        self.gridlines_cb = QCheckBox("Show gridlines")
        self.gridlines_cb.setChecked(self._current_settings.get("show_gridlines", True))
        checkbox_grid.addWidget(self.gridlines_cb, 0, 1)

        self.crosshair_cb = QCheckBox("Show crosshair")
        self.crosshair_cb.setChecked(self._current_settings.get("show_crosshair", True))
        checkbox_grid.addWidget(self.crosshair_cb, 1, 0)

        self.tooltip_cb = QCheckBox("Show hover tooltip")
        self.tooltip_cb.setChecked(self._current_settings.get("show_hover_tooltip", True))
        checkbox_grid.addWidget(self.tooltip_cb, 1, 1)

        layout.addLayout(checkbox_grid)

        layout.addStretch()

        # -- Buttons ------------------------------------------------------
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

    def _on_threshold_toggled(self, checked: bool):
        self.threshold_input.setEnabled(checked)

    def _save_settings(self):
        self.result = {
            "show_threshold": self.show_threshold_cb.isChecked(),
            "threshold_value": self.threshold_input.value(),
            "show_recession_bands": self.recession_cb.isChecked(),
            "show_gridlines": self.gridlines_cb.isChecked(),
            "show_crosshair": self.crosshair_cb.isChecked(),
            "show_hover_tooltip": self.tooltip_cb.isChecked(),
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
