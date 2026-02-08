"""Yield Curve Toolbar Widget - Top control bar for yield curve module."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import (
    LazyThemeMixin,
    ThemedDialog,
    DateInputWidget,
    NoScrollComboBox,
)
from app.services.theme_stylesheet_service import ThemeStylesheetService


# Overlay period presets
OVERLAY_PERIODS = [
    ("1W", "1 Week Ago"),
    ("1M", "1 Month Ago"),
    ("6M", "6 Months Ago"),
    ("1Y", "1 Year Ago"),
    ("2Y", "2 Years Ago"),
    ("5Y", "5 Years Ago"),
]


class CustomDateDialog(ThemedDialog):
    """Dialog for selecting a custom overlay date."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._selected_date: Optional[str] = None
        super().__init__(theme_manager, "Custom Date Overlay", parent, min_width=350)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        desc = QLabel("Enter a date to overlay on the yield curve:")
        desc.setWordWrap(True)
        desc.setObjectName("description_label")
        layout.addWidget(desc)

        # Date input row
        date_row = QHBoxLayout()
        date_row.setSpacing(10)

        date_label = QLabel("Date:")
        date_label.setObjectName("field_label")
        date_row.addWidget(date_label)

        self.date_input = DateInputWidget()
        self.date_input.setFixedWidth(150)
        self.date_input.setFixedHeight(36)
        date_row.addWidget(self.date_input)

        date_row.addStretch()
        layout.addLayout(date_row)

        info = QLabel("Format: YYYY-MM-DD. Date must be in the past.")
        info.setObjectName("noteLabel")
        layout.addWidget(info)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(100, 36)
        ok_btn.setObjectName("defaultButton")
        ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def _on_ok(self):
        date_text = self.date_input.text().strip()
        if date_text and len(date_text) == 10:
            self._selected_date = date_text
            self.accept()

    def get_date(self) -> Optional[str]:
        return self._selected_date


class YieldCurveToolbar(LazyThemeMixin, QWidget):
    """
    Top control bar for the Yield Curve module.

    Contains: Home button, Interpolation dropdown, Overlay period buttons,
    Custom date button, Clear button.
    """

    # Signals
    home_clicked = Signal()
    interpolation_changed = Signal(str)  # "Cubic Spline" or "Nelson-Siegel"
    overlay_toggled = Signal(str, bool)  # period key, active state
    custom_date_selected = Signal(str)  # YYYY-MM-DD
    overlay_cleared = Signal()


    INTERPOLATION_OPTIONS = ["Cubic Spline", "Nelson-Siegel", "Linear"]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        self._overlay_buttons: dict[str, QPushButton] = {}
        self._active_overlays: set[str] = set()

        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup toolbar layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Home button
        self.home_btn = QPushButton("Home")
        self.home_btn.setMinimumWidth(70)
        self.home_btn.setMaximumWidth(100)
        self.home_btn.setFixedHeight(40)
        self.home_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.home_btn.setObjectName("home_btn")
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        # Separator
        sep = QLabel("|")
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # Interpolation dropdown
        interp_label = QLabel("Fit:")
        interp_label.setObjectName("control_label")
        layout.addWidget(interp_label)

        self.interp_combo = NoScrollComboBox()
        self.interp_combo.setMinimumWidth(120)
        self.interp_combo.setMaximumWidth(160)
        self.interp_combo.setFixedHeight(40)
        self.interp_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.interp_combo.addItems(self.INTERPOLATION_OPTIONS)
        self.interp_combo.currentTextChanged.connect(self.interpolation_changed.emit)
        layout.addWidget(self.interp_combo)

        # Separator
        sep2 = QLabel("|")
        sep2.setObjectName("separator")
        layout.addWidget(sep2)

        # Overlay period buttons
        for key, tooltip in OVERLAY_PERIODS:
            btn = QPushButton(key)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(40)
            btn.setMinimumWidth(40)
            btn.setMaximumWidth(55)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn.setCheckable(True)
            btn.setObjectName("overlay_btn")
            btn.clicked.connect(lambda checked, k=key: self._on_overlay_toggled(k, checked))
            layout.addWidget(btn)
            self._overlay_buttons[key] = btn

        # Custom date button
        self.custom_btn = QPushButton("Custom")
        self.custom_btn.setFixedHeight(40)
        self.custom_btn.setMinimumWidth(60)
        self.custom_btn.setMaximumWidth(80)
        self.custom_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.custom_btn.clicked.connect(self._on_custom_clicked)
        layout.addWidget(self.custom_btn)

        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedHeight(40)
        self.clear_btn.setMinimumWidth(50)
        self.clear_btn.setMaximumWidth(70)
        self.clear_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        layout.addWidget(self.clear_btn)

        layout.addStretch(1)

    def _on_overlay_toggled(self, key: str, checked: bool):
        """Handle overlay button toggle."""
        if checked:
            self._active_overlays.add(key)
        else:
            self._active_overlays.discard(key)
        self.overlay_toggled.emit(key, checked)
        self._update_button_styles()

    def _on_custom_clicked(self):
        """Open custom date picker dialog."""
        dialog = CustomDateDialog(self.theme_manager, self)
        if dialog.exec():
            date_str = dialog.get_date()
            if date_str:
                self.custom_date_selected.emit(date_str)

    def _on_clear_clicked(self):
        """Clear all overlay selections."""
        self._active_overlays.clear()
        for btn in self._overlay_buttons.values():
            btn.setChecked(False)
        self.overlay_cleared.emit()
        self._update_button_styles()

    def get_interpolation_method(self) -> str:
        """Get current interpolation method name."""
        return self.interp_combo.currentText()

    def _update_button_styles(self):
        """Re-apply theme to update toggle highlight state."""
        self._apply_theme()

    def _apply_theme(self):
        """Apply theme-specific styling."""
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if self.theme_manager.current_theme == "dark":
            bg_hover = "#3d3d3d"
        elif self.theme_manager.current_theme == "light":
            bg_hover = "#e8e8e8"
        else:  # bloomberg
            bg_hover = "#1a2838"

        # Active overlay button style
        active_bg = c["accent"]
        active_text = c["text_on_accent"]

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg']};
                color: {c['text']};
            }}
            QLabel {{
                color: {c['text_muted']};
                font-size: 13px;
                background: transparent;
            }}
            QLabel#control_label {{
                color: {c['text']};
                font-size: 14px;
                font-weight: 500;
                background: transparent;
            }}
            QLabel#separator {{
                color: {c['border']};
                font-size: 18px;
                background: transparent;
                padding: 0 2px;
            }}
            QComboBox {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QComboBox:hover {{
                border-color: {c['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid {c['text']};
                margin-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['bg_header']};
                color: {c['text']};
                selection-background-color: {c['accent']};
                selection-color: {c['text_on_accent']};
                font-size: 14px;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                min-height: 24px;
            }}
            QPushButton {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
                border-color: {c['accent']};
            }}
            QPushButton:pressed {{
                background-color: {c['bg']};
            }}
            QPushButton#overlay_btn {{
                font-weight: bold;
            }}
            QPushButton#overlay_btn:checked {{
                background-color: {active_bg};
                color: {active_text};
                border-color: {active_bg};
            }}
        """)
