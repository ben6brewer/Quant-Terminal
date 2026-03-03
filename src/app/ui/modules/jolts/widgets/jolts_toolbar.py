"""JOLTS Toolbar - Home, lookback, openings info, settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import NoScrollComboBox
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from app.services.theme_stylesheet_service import ThemeStylesheetService


LOOKBACK_OPTIONS = [
    ("1Y", 12),
    ("2Y", 24),
    ("5Y", 60),
    ("10Y", 120),
    ("20Y", 240),
    ("Max", None),
    ("Custom", -1),
]


class JoltsToolbar(LazyThemeMixin, QWidget):
    """Toolbar with home, lookback, openings info, and settings."""

    home_clicked = Signal()
    lookback_changed = Signal(str)
    settings_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._previous_lookback_index = 2  # Default: 5Y
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        self.setObjectName("moduleToolbar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.home_btn = QPushButton("Home")
        self.home_btn.setMinimumWidth(70)
        self.home_btn.setMaximumWidth(100)
        self.home_btn.setFixedHeight(40)
        self.home_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        sep1 = QLabel("|")
        sep1.setObjectName("separator")
        layout.addWidget(sep1)

        lookback_label = QLabel("Lookback:")
        lookback_label.setObjectName("control_label")
        layout.addWidget(lookback_label)

        self.lookback_combo = NoScrollComboBox()
        self.lookback_combo.setMinimumWidth(110)
        self.lookback_combo.setMaximumWidth(160)
        self.lookback_combo.setFixedHeight(40)
        self.lookback_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, months in LOOKBACK_OPTIONS:
            self.lookback_combo.addItem(label, months)
        self.lookback_combo.setCurrentIndex(2)  # 5Y
        self.lookback_combo.currentIndexChanged.connect(self._on_lookback_changed)
        layout.addWidget(self.lookback_combo)

        sep2 = QLabel("|")
        sep2.setObjectName("separator")
        layout.addWidget(sep2)

        self.openings_label = QLabel("Openings: --")
        self.openings_label.setObjectName("info_label")
        layout.addWidget(self.openings_label)

        sep3 = QLabel("|")
        sep3.setObjectName("separator")
        layout.addWidget(sep3)

        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

        layout.addStretch(1)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setMinimumWidth(70)
        self.settings_btn.setMaximumWidth(100)
        self.settings_btn.setFixedHeight(40)
        self.settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def _on_lookback_changed(self, index: int):
        data = self.lookback_combo.currentData()

        if data == -1:
            from app.ui.modules.cpi.widgets.custom_start_date_dialog import CustomStartDateDialog
            dialog = CustomStartDateDialog(self.theme_manager, parent=self.window())
            if dialog.exec():
                date_str = dialog.get_start_date()
                if date_str:
                    self.lookback_combo.blockSignals(True)
                    self.lookback_combo.setItemText(index, date_str)
                    self.lookback_combo.blockSignals(False)
                    self._previous_lookback_index = index
                    self.lookback_changed.emit(date_str)
            else:
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(self._previous_lookback_index)
                self.lookback_combo.blockSignals(False)
            return

        self._previous_lookback_index = index
        self.lookback_changed.emit(self.lookback_combo.currentText())

    def set_active_lookback(self, lookback: str):
        for i in range(self.lookback_combo.count()):
            if self.lookback_combo.itemText(i) == lookback:
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(i)
                self._previous_lookback_index = i
                self.lookback_combo.blockSignals(False)
                return

    def update_info(self, openings=None):
        if openings is not None:
            val_str = f"{openings/1000:.2f}M" if openings >= 1000 else f"{openings:,.0f}K"
            self.openings_label.setText(f"Openings: {val_str}")
        from datetime import datetime
        self.updated_label.setText(
            f"Updated: {datetime.now().strftime('%m/%d %I:%M%p').lower()}"
        )

    def _apply_theme(self):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if self.theme_manager.current_theme == "dark":
            bg_hover = "#3d3d3d"
        elif self.theme_manager.current_theme == "light":
            bg_hover = "#e8e8e8"
        else:
            bg_hover = "#1a2838"

        self.setStyleSheet(f"""
            #moduleToolbar {{
                background-color: {c['bg']};
            }}
            QLabel {{
                color: {c['text_muted']};
                font-size: 13px;
                background: transparent;
            }}
            QLabel#control_label {{
                color: {c['text']};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }}
            QLabel#info_label {{
                color: {c['text']};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }}
            QLabel#info_label_muted {{
                color: {c['text_muted']};
                font-size: 12px;
                background: transparent;
            }}
            QLabel#separator {{
                color: {c['border']};
                font-size: 18px;
                background: transparent;
                padding: 0 2px;
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
            QComboBox {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 13px;
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
                font-size: 13px;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
            }}
        """)
