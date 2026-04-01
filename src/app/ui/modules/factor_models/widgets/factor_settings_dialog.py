"""Factor Models Settings Dialog — display and statistical settings."""

from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QCheckBox,
    QLineEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator

from app.ui.widgets.common import ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService


class FactorSettingsDialog(ThemedDialog):
    """Settings dialog for the Factor Models module."""

    def __init__(self, theme_manager, current_settings: dict, parent=None):
        self._current_settings = current_settings
        self.result = None
        super().__init__(theme_manager, "Factor Models Settings", parent, min_width=440)

    def _setup_content(self, layout):
        s = self._current_settings

        # ── Section Visibility ──────────────────────────────────────
        header_1 = QLabel("Section Visibility")
        header_1.setObjectName("sectionHeader")
        layout.addWidget(header_1)
        layout.addSpacing(8)

        self._gof_cb = QCheckBox("Show Goodness of Fit")
        self._gof_cb.setChecked(s.get("show_goodness_of_fit", True))
        layout.addWidget(self._gof_cb)

        self._diag_cb = QCheckBox("Show Diagnostics")
        self._diag_cb.setChecked(s.get("show_diagnostics", True))
        layout.addWidget(self._diag_cb)

        layout.addSpacing(16)

        # ── Coefficient Columns ─────────────────────────────────────
        header_2 = QLabel("Coefficient Columns")
        header_2.setObjectName("sectionHeader")
        layout.addWidget(header_2)
        layout.addSpacing(8)

        col_grid = QGridLayout()
        col_grid.setSpacing(8)

        self._col_coeff_cb = QCheckBox("Coefficient")
        self._col_coeff_cb.setChecked(s.get("show_col_coefficient", True))
        col_grid.addWidget(self._col_coeff_cb, 0, 0)

        self._col_se_cb = QCheckBox("Std Error")
        self._col_se_cb.setChecked(s.get("show_col_std_error", True))
        col_grid.addWidget(self._col_se_cb, 0, 1)

        self._col_t_cb = QCheckBox("T-Stat")
        self._col_t_cb.setChecked(s.get("show_col_t_stat", True))
        col_grid.addWidget(self._col_t_cb, 1, 0)

        self._col_p_cb = QCheckBox("P-Value")
        self._col_p_cb.setChecked(s.get("show_col_p_value", True))
        col_grid.addWidget(self._col_p_cb, 1, 1)

        self._col_ci_cb = QCheckBox("Confidence Interval")
        self._col_ci_cb.setChecked(s.get("show_col_ci", True))
        col_grid.addWidget(self._col_ci_cb, 2, 0)

        layout.addLayout(col_grid)

        layout.addSpacing(16)

        # ── Statistical Settings ────────────────────────────────────
        header_3 = QLabel("Statistical Settings")
        header_3.setObjectName("sectionHeader")
        layout.addWidget(header_3)
        layout.addSpacing(8)

        self._sig_cb = QCheckBox("Show only significant factors")
        self._sig_cb.setChecked(s.get("show_only_significant", False))
        layout.addWidget(self._sig_cb)

        layout.addSpacing(8)

        # Confidence level input
        ci_row = QHBoxLayout()
        ci_label = QLabel("Confidence Level:")
        ci_row.addWidget(ci_label)

        self._ci_input = QLineEdit()
        self._ci_input.setFixedWidth(50)
        self._ci_input.setAlignment(Qt.AlignCenter)
        self._ci_input.setValidator(QIntValidator(50, 99))
        ci_pct = int(round(s.get("confidence_level", 0.95) * 100))
        self._ci_input.setText(str(ci_pct))
        ci_row.addWidget(self._ci_input)

        pct_label = QLabel("%")
        ci_row.addWidget(pct_label)
        ci_row.addStretch()
        layout.addLayout(ci_row)

        layout.addSpacing(4)

        note = QLabel("Changing confidence level will re-run the regression.")
        note.setObjectName("noteLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()

        # ── Buttons ─────────────────────────────────────────────────
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

    def _save_settings(self):
        ci_text = self._ci_input.text().strip()
        try:
            ci_pct = int(ci_text)
            ci_pct = max(50, min(99, ci_pct))
        except ValueError:
            ci_pct = 95

        self.result = {
            "show_goodness_of_fit": self._gof_cb.isChecked(),
            "show_diagnostics": self._diag_cb.isChecked(),
            "show_col_coefficient": self._col_coeff_cb.isChecked(),
            "show_col_std_error": self._col_se_cb.isChecked(),
            "show_col_t_stat": self._col_t_cb.isChecked(),
            "show_col_p_value": self._col_p_cb.isChecked(),
            "show_col_ci": self._col_ci_cb.isChecked(),
            "show_only_significant": self._sig_cb.isChecked(),
            "confidence_level": ci_pct / 100.0,
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
            QLabel#noteLabel {{
                color: {c['text_muted']};
                font-size: 11px;
                font-style: italic;
                background: transparent;
            }}
            QLineEdit {{
                color: {c['text']};
                background-color: {c['bg']};
                border: 1px solid {c.get('border', '#333333')};
                border-radius: 4px;
                padding: 4px;
            }}
        """
        self.setStyleSheet(self.styleSheet() + additional_style)
