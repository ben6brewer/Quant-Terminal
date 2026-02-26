"""CPI Settings Dialog - Configure display, line, and breakdown settings."""

from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QCheckBox,
    QColorDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.ui.widgets.common import ThemedDialog, NoScrollComboBox
from app.services.theme_stylesheet_service import ThemeStylesheetService


class CpiSettingsDialog(ThemedDialog):
    """Settings dialog for the CPI module."""

    LINE_STYLES = {
        "Solid": Qt.SolidLine,
        "Dashed": Qt.DashLine,
        "Dotted": Qt.DotLine,
        "Dash-Dot": Qt.DashDotLine,
    }

    LINE_STYLE_NAMES = {v: k for k, v in LINE_STYLES.items()}

    def __init__(self, theme_manager, current_settings: dict, parent=None):
        self._current_settings = current_settings
        self._line_color = current_settings.get("line_color", None)
        self.result = None
        super().__init__(theme_manager, "CPI Settings", parent, min_width=420)

    def _setup_content(self, layout):
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

        # -- Line Settings ----------------------------------------------------
        line_header = QLabel("Line Settings")
        line_header.setObjectName("sectionHeader")
        layout.addWidget(line_header)

        layout.addSpacing(8)

        # Line color row
        color_row = QHBoxLayout()
        color_row.setSpacing(8)

        self.line_use_theme_check = QCheckBox("Theme Default")
        self.line_use_theme_check.setChecked(self._line_color is None)
        self.line_use_theme_check.toggled.connect(self._on_line_theme_toggled)
        color_row.addWidget(self.line_use_theme_check)

        color_row.addSpacing(12)

        color_label = QLabel("Color:")
        color_row.addWidget(color_label)

        self.line_color_btn = QPushButton("Color")
        self.line_color_btn.setFixedWidth(65)
        self.line_color_btn.clicked.connect(self._on_line_color_clicked)
        color_row.addWidget(self.line_color_btn)

        self.line_color_preview = QLabel("\u25cf")  # bullet
        self.line_color_preview.setFixedWidth(24)
        self._update_color_preview()
        color_row.addWidget(self.line_color_preview)

        color_row.addStretch()
        layout.addLayout(color_row)

        layout.addSpacing(8)

        # Width + Style row
        line_row = QHBoxLayout()
        line_row.setSpacing(8)

        width_label = QLabel("Width:")
        line_row.addWidget(width_label)

        self.width_combo = NoScrollComboBox()
        for w in [1, 2, 3, 4]:
            self.width_combo.addItem(str(w), w)
        self.width_combo.setFixedHeight(32)
        self.width_combo.setMinimumWidth(60)
        current_width = self._current_settings.get("line_width", 2)
        for i in range(self.width_combo.count()):
            if self.width_combo.itemData(i) == current_width:
                self.width_combo.setCurrentIndex(i)
                break
        line_row.addWidget(self.width_combo)

        line_row.addSpacing(20)

        style_label = QLabel("Style:")
        line_row.addWidget(style_label)

        self.line_style_combo = NoScrollComboBox()
        self.line_style_combo.addItems(list(self.LINE_STYLES.keys()))
        self.line_style_combo.setFixedHeight(32)
        self.line_style_combo.setMinimumWidth(90)

        current_style = self._current_settings.get("line_style", Qt.SolidLine)
        style_name = self.LINE_STYLE_NAMES.get(current_style, "Solid")
        style_idx = self.line_style_combo.findText(style_name)
        if style_idx >= 0:
            self.line_style_combo.setCurrentIndex(style_idx)

        line_row.addWidget(self.line_style_combo)
        line_row.addStretch()
        layout.addLayout(line_row)

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

        self._apply_extra_theme()

    # -- Color Picker ---------------------------------------------------------

    def _update_color_preview(self):
        if self._line_color:
            r, g, b = self._line_color
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({r}, {g}, {b});"
            )
        else:
            self.line_color_preview.setStyleSheet(
                "font-size: 24px; color: #888888;"
            )

    def _on_line_theme_toggled(self, checked: bool):
        if checked:
            self._line_color = None
            self._update_color_preview()

    def _on_line_color_clicked(self):
        self.line_use_theme_check.setChecked(False)

        if self._line_color:
            current = QColor(*self._line_color)
        else:
            current = QColor(128, 128, 128)

        color = QColorDialog.getColor(current, self, "Select Line Color")
        if color.isValid():
            self._line_color = (color.red(), color.green(), color.blue())
            self._update_color_preview()

    # -- Save / Get -----------------------------------------------------------

    def _save_settings(self):
        self.result = {
            "show_gridlines": self.gridlines_cb.isChecked(),
            "show_reference_lines": self.ref_lines_cb.isChecked(),
            "show_crosshair": self.crosshair_cb.isChecked(),
            "show_value_label": self.value_label_cb.isChecked(),
            "show_date_label": self.date_label_cb.isChecked(),
            "line_width": self.width_combo.currentData(),
            "line_color": self._line_color,
            "line_style": self.LINE_STYLES[self.line_style_combo.currentText()],
            "show_headline_overlay": self.headline_overlay_cb.isChecked(),
            "show_legend": self.legend_cb.isChecked(),
            "show_hover_tooltip": self.hover_tooltip_cb.isChecked(),
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
        """)
