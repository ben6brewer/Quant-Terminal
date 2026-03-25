"""Custom Model Dialog — create / edit / delete user-defined factor models."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QCheckBox,
    QFrame,
    QWidget,
)
from PySide6.QtCore import Qt

from app.ui.widgets.common import ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService

from ..services.custom_model_store import FACTOR_CATALOG, CustomModelStore
from ..services.model_definitions import FactorModelSpec


class CustomModelDialog(ThemedDialog):
    """Dialog for creating or editing a custom factor model.

    Three vertical columns (Fama-French, Q-Factor, AQR) of selectable factors.
    Market factor (Mkt-RF) is always included automatically.
    """

    def __init__(
        self,
        theme_manager,
        parent=None,
        edit_spec: Optional[FactorModelSpec] = None,
    ):
        self._edit_spec = edit_spec
        self._result: Optional[tuple[str, list[str]]] = None
        self._deleted = False
        self._checkboxes: dict[str, QCheckBox] = {}  # factor_col -> checkbox

        title = "Edit Custom Model" if edit_spec else "Create Custom Model"
        super().__init__(theme_manager, title, parent, min_width=520)

    # ── Content ──────────────────────────────────────────────────────────

    def _setup_content(self, layout: QVBoxLayout):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        # Name field
        name_row = QHBoxLayout()
        name_label = QLabel("Name:")
        name_label.setFixedWidth(50)
        name_label.setObjectName("field_label")
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Value + Momentum")
        self._name_input.setFixedHeight(36)
        name_row.addWidget(name_label)
        name_row.addWidget(self._name_input)
        layout.addLayout(name_row)

        # Market factor note
        mkt_note = QLabel("Market factor (Mkt-RF) is always included.")
        mkt_note.setObjectName("mkt_note")
        mkt_note.setAlignment(Qt.AlignLeft)
        layout.addWidget(mkt_note)

        layout.addSpacing(4)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)

        layout.addSpacing(4)

        # Three-column factor selection
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(16)

        for source_name, factors in FACTOR_CATALOG.items():
            col = QVBoxLayout()
            col.setSpacing(6)

            # Header
            header = QLabel(source_name)
            header.setObjectName("column_header")
            header.setAlignment(Qt.AlignCenter)
            col.addWidget(header)

            # Subtitle for AQR
            if source_name == "AQR":
                subtitle = QLabel("(Monthly Only)")
                subtitle.setObjectName("column_subtitle")
                subtitle.setAlignment(Qt.AlignCenter)
                col.addWidget(subtitle)

            # Factor checkboxes
            for factor_col, display_name in factors:
                cb = QCheckBox(f"{factor_col} \u2014 {display_name}")
                cb.setObjectName("factor_checkbox")
                cb.stateChanged.connect(self._on_factor_toggled)
                col.addWidget(cb)
                self._checkboxes[factor_col] = cb

            col.addStretch(1)

            # Wrap in a widget for border
            col_widget = QWidget()
            col_widget.setObjectName("factor_column")
            col_widget.setLayout(col)
            columns_layout.addWidget(col_widget)

        layout.addLayout(columns_layout)

        # Frequency note (dynamic)
        self._freq_note = QLabel("")
        self._freq_note.setObjectName("freq_note")
        self._freq_note.hide()
        layout.addWidget(self._freq_note)

        layout.addSpacing(4)

        # Error label
        self._error_label = QLabel("")
        self._error_label.setObjectName("error_label")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        layout.addSpacing(8)

        # Buttons
        btn_row = QHBoxLayout()

        # Delete button (edit mode only)
        if self._edit_spec:
            self._delete_btn = QPushButton("Delete")
            self._delete_btn.setFixedHeight(34)
            self._delete_btn.setMinimumWidth(80)
            self._delete_btn.setObjectName("delete_btn")
            self._delete_btn.clicked.connect(self._on_delete)
            btn_row.addWidget(self._delete_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        btn_row.addSpacing(8)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedHeight(34)
        ok_btn.setMinimumWidth(80)
        ok_btn.setObjectName("ok_btn")
        ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

        # Pre-populate if editing
        if self._edit_spec:
            self._name_input.setText(self._edit_spec.name)
            for factor_col in self._edit_spec.factors:
                if factor_col in self._checkboxes:
                    self._checkboxes[factor_col].setChecked(True)

        self._apply_extra_theme()

    # ── Signals ──────────────────────────────────────────────────────────

    def _on_factor_toggled(self, _state: int):
        """Update frequency note when AQR factors are toggled."""
        aqr_factors = {"BAB", "QMJ", "HML_DEVIL"}
        has_aqr = any(
            self._checkboxes[f].isChecked()
            for f in aqr_factors
            if f in self._checkboxes
        )
        if has_aqr:
            self._freq_note.setText(
                "Note: AQR factors restrict this model to Monthly frequency only."
            )
            self._freq_note.show()
        else:
            self._freq_note.hide()

    def _on_ok(self):
        """Validate and accept."""
        name = self._name_input.text().strip()
        if not name:
            self._show_error("Please enter a model name.")
            return

        # Check uniqueness
        exclude_key = self._edit_spec.key if self._edit_spec else ""
        existing = CustomModelStore.existing_names(exclude_key)
        if name in existing:
            self._show_error(f"A custom model named \"{name}\" already exists.")
            return

        selected = [col for col, cb in self._checkboxes.items() if cb.isChecked()]
        if not selected:
            self._show_error("Select at least one factor.")
            return

        self._result = (name, selected)
        self.accept()

    def _on_delete(self):
        """Delete the model being edited."""
        self._deleted = True
        self.accept()

    def _show_error(self, message: str):
        self._error_label.setText(message)
        self._error_label.show()

    # ── Public API ───────────────────────────────────────────────────────

    def get_result(self) -> Optional[tuple[str, list[str]]]:
        """Return (name, factors_list) or None if cancelled."""
        return self._result

    @property
    def was_deleted(self) -> bool:
        return self._deleted

    # ── Theme ────────────────────────────────────────────────────────────

    def _apply_extra_theme(self):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if self.theme_manager.current_theme == "dark":
            ok_hover = "#00bfe6"
            del_bg = "#cc3333"
            del_hover = "#dd4444"
        elif self.theme_manager.current_theme == "light":
            ok_hover = "#0055aa"
            del_bg = "#cc3333"
            del_hover = "#dd4444"
        else:
            ok_hover = "#e67300"
            del_bg = "#cc3333"
            del_hover = "#dd4444"

        self.setStyleSheet(self.styleSheet() + f"""
            QLabel#field_label {{
                color: {c['text']};
                font-size: 14px;
                background: transparent;
            }}
            QLabel#mkt_note {{
                color: {c['text_muted']};
                font-size: 12px;
                font-style: italic;
                background: transparent;
                padding: 2px 0;
            }}
            QLabel#column_header {{
                color: {c['accent']};
                font-size: 13px;
                font-weight: bold;
                background: transparent;
                padding: 4px 0;
            }}
            QLabel#column_subtitle {{
                color: {c['text_muted']};
                font-size: 11px;
                background: transparent;
                margin-top: -4px;
                padding-bottom: 2px;
            }}
            QLabel#freq_note {{
                color: {c['accent']};
                font-size: 12px;
                background: transparent;
                padding: 4px 0;
            }}
            QLabel#error_label {{
                color: #ff4444;
                font-size: 12px;
                background: transparent;
                padding: 2px 0;
            }}
            QWidget#factor_column {{
                background-color: {c['bg_alt']};
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 8px;
            }}
            QCheckBox#factor_checkbox {{
                color: {c['text']};
                font-size: 12px;
                background: transparent;
                spacing: 6px;
                padding: 2px 0;
            }}
            QCheckBox#factor_checkbox::indicator {{
                width: 14px;
                height: 14px;
            }}
            QFrame#separator {{
                color: {c['border']};
            }}
            QLineEdit {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 10px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
            QPushButton {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                border-color: {c['accent']};
            }}
            QPushButton#ok_btn {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                font-weight: bold;
                border: 1px solid {c['accent']};
            }}
            QPushButton#ok_btn:hover {{
                background-color: {ok_hover};
                border-color: {ok_hover};
            }}
            QPushButton#delete_btn {{
                background-color: {del_bg};
                color: #ffffff;
                font-weight: bold;
                border: 1px solid {del_bg};
            }}
            QPushButton#delete_btn:hover {{
                background-color: {del_hover};
                border-color: {del_hover};
            }}
        """)
