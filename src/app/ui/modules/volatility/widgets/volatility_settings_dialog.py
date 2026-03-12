"""Volatility Settings Dialog - Configure thresholds and display settings."""

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


class VolatilitySettingsDialog(ThemedDialog):
    """Settings dialog for the Volatility module."""

    def __init__(self, theme_manager, current_settings: dict, parent=None):
        self._current_settings = current_settings
        self.result = None
        super().__init__(theme_manager, "Volatility Settings", parent, min_width=420)

    def _setup_content(self, layout):
        # -- Series -------------------------------------------------------
        series_header = QLabel("Series")
        series_header.setObjectName("sectionHeader")
        layout.addWidget(series_header)

        layout.addSpacing(8)

        series_grid = QGridLayout()
        series_grid.setSpacing(8)

        self.vix_cb = QCheckBox("Show VIX")
        self.vix_cb.setChecked(self._current_settings.get("show_vix", True))
        series_grid.addWidget(self.vix_cb, 0, 0)

        self.nasdaq_vol_cb = QCheckBox("Show NASDAQ Vol")
        self.nasdaq_vol_cb.setChecked(self._current_settings.get("show_nasdaq_vol", True))
        series_grid.addWidget(self.nasdaq_vol_cb, 0, 1)

        self.vol_3m_cb = QCheckBox("Show 3M Vol")
        self.vol_3m_cb.setChecked(self._current_settings.get("show_3m_vol", False))
        series_grid.addWidget(self.vol_3m_cb, 1, 0)

        self.russell_vol_cb = QCheckBox("Show Russell Vol")
        self.russell_vol_cb.setChecked(self._current_settings.get("show_russell_vol", False))
        series_grid.addWidget(self.russell_vol_cb, 1, 1)

        self.oil_vol_cb = QCheckBox("Show Oil Vol")
        self.oil_vol_cb.setChecked(self._current_settings.get("show_oil_vol", False))
        series_grid.addWidget(self.oil_vol_cb, 2, 0)

        self.djia_vol_cb = QCheckBox("Show DJIA Vol")
        self.djia_vol_cb.setChecked(self._current_settings.get("show_djia_vol", False))
        series_grid.addWidget(self.djia_vol_cb, 2, 1)

        self.em_vol_cb = QCheckBox("Show EM Vol")
        self.em_vol_cb.setChecked(self._current_settings.get("show_em_vol", False))
        series_grid.addWidget(self.em_vol_cb, 3, 0)

        self.move_cb = QCheckBox("Show MOVE")
        self.move_cb.setChecked(self._current_settings.get("show_move", True))
        series_grid.addWidget(self.move_cb, 3, 1)

        layout.addLayout(series_grid)

        layout.addSpacing(16)

        # -- Thresholds ---------------------------------------------------
        threshold_header = QLabel("Thresholds")
        threshold_header.setObjectName("sectionHeader")
        layout.addWidget(threshold_header)

        layout.addSpacing(8)

        self.show_thresholds_cb = QCheckBox("Show threshold lines")
        self.show_thresholds_cb.setChecked(self._current_settings.get("show_thresholds", True))
        self.show_thresholds_cb.toggled.connect(self._on_thresholds_toggled)
        layout.addWidget(self.show_thresholds_cb)

        layout.addSpacing(4)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Threshold 1:"))
        self.threshold_1_input = ValidatedNumericLineEdit(
            min_value=0.0, max_value=200.0, decimals=0
        )
        self.threshold_1_input.setFixedWidth(80)
        self.threshold_1_input.setValue(self._current_settings.get("threshold_1", 20))
        row1.addWidget(self.threshold_1_input)
        row1.addStretch()
        layout.addLayout(row1)

        layout.addSpacing(4)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Threshold 2:"))
        self.threshold_2_input = ValidatedNumericLineEdit(
            min_value=0.0, max_value=200.0, decimals=0
        )
        self.threshold_2_input.setFixedWidth(80)
        self.threshold_2_input.setValue(self._current_settings.get("threshold_2", 30))
        row2.addWidget(self.threshold_2_input)
        row2.addStretch()
        layout.addLayout(row2)

        self._on_thresholds_toggled(self.show_thresholds_cb.isChecked())

        layout.addSpacing(16)

        # -- Display ------------------------------------------------------
        display_header = QLabel("Display")
        display_header.setObjectName("sectionHeader")
        layout.addWidget(display_header)

        layout.addSpacing(8)

        display_grid = QGridLayout()
        display_grid.setSpacing(8)

        self.recession_cb = QCheckBox("Show recession shading")
        self.recession_cb.setChecked(self._current_settings.get("show_recession_bands", True))
        display_grid.addWidget(self.recession_cb, 0, 0)

        self.gridlines_cb = QCheckBox("Show gridlines")
        self.gridlines_cb.setChecked(self._current_settings.get("show_gridlines", True))
        display_grid.addWidget(self.gridlines_cb, 0, 1)

        self.crosshair_cb = QCheckBox("Show crosshair")
        self.crosshair_cb.setChecked(self._current_settings.get("show_crosshair", True))
        display_grid.addWidget(self.crosshair_cb, 1, 0)

        self.legend_cb = QCheckBox("Show legend")
        self.legend_cb.setChecked(self._current_settings.get("show_legend", True))
        display_grid.addWidget(self.legend_cb, 1, 1)

        self.tooltip_cb = QCheckBox("Show hover tooltip")
        self.tooltip_cb.setChecked(self._current_settings.get("show_hover_tooltip", True))
        display_grid.addWidget(self.tooltip_cb, 2, 0)

        layout.addLayout(display_grid)

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

    def _on_thresholds_toggled(self, checked: bool):
        self.threshold_1_input.setEnabled(checked)
        self.threshold_2_input.setEnabled(checked)

    def _save_settings(self):
        self.result = {
            "show_vix": self.vix_cb.isChecked(),
            "show_3m_vol": self.vol_3m_cb.isChecked(),
            "show_oil_vol": self.oil_vol_cb.isChecked(),
            "show_nasdaq_vol": self.nasdaq_vol_cb.isChecked(),
            "show_russell_vol": self.russell_vol_cb.isChecked(),
            "show_djia_vol": self.djia_vol_cb.isChecked(),
            "show_em_vol": self.em_vol_cb.isChecked(),
            "show_move": self.move_cb.isChecked(),
            "show_thresholds": self.show_thresholds_cb.isChecked(),
            "threshold_1": self.threshold_1_input.value(),
            "threshold_2": self.threshold_2_input.value(),
            "show_recession_bands": self.recession_cb.isChecked(),
            "show_gridlines": self.gridlines_cb.isChecked(),
            "show_crosshair": self.crosshair_cb.isChecked(),
            "show_legend": self.legend_cb.isChecked(),
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
