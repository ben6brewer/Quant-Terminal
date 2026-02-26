"""CPI Toolbar - Home button, view tabs, lookback dropdown, info labels, settings."""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QButtonGroup,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import NoScrollComboBox
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from app.services.theme_stylesheet_service import ThemeStylesheetService


# Lookback options: (label, months)  — -1 = custom
LOOKBACK_OPTIONS = [
    ("1Y", 12),
    ("2Y", 24),
    ("5Y", 60),
    ("10Y", 120),
    ("20Y", 240),
    ("Max", None),
    ("Custom", -1),
]


class CpiToolbar(LazyThemeMixin, QWidget):
    """Toolbar with home button, view tabs, lookback dropdown, info bar, and settings."""

    home_clicked = Signal()
    view_changed = Signal(int)       # 0=Headline, 1=Breakdown
    lookback_changed = Signal(str)   # "1Y", "2Y", … or ISO date string
    settings_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._previous_lookback_index = 1  # Default: 2Y
        self._custom_start_date = None
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup toolbar layout."""
        self.setObjectName("cpiToolbar")
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

        # View tab buttons
        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)

        view_names = ["Headline", "Breakdown"]
        self._view_buttons = []
        for i, name in enumerate(view_names):
            btn = QPushButton(name)
            btn.setObjectName("viewTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumWidth(110)
            btn.setFixedHeight(40)
            if i == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, idx=i: self.view_changed.emit(idx))
            layout.addWidget(btn)
            self.view_group.addButton(btn)
            self._view_buttons.append(btn)

        # Separator
        sep1 = QLabel("|")
        sep1.setObjectName("separator")
        layout.addWidget(sep1)

        # Lookback dropdown
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
        self.lookback_combo.setCurrentIndex(1)  # Default: 2Y
        self.lookback_combo.currentIndexChanged.connect(self._on_lookback_changed)
        layout.addWidget(self.lookback_combo)

        # Separator
        sep2 = QLabel("|")
        sep2.setObjectName("separator")
        layout.addWidget(sep2)

        # Info labels
        self.headline_label = QLabel("Headline: --")
        self.headline_label.setObjectName("info_label")
        layout.addWidget(self.headline_label)

        sep3 = QLabel("|")
        sep3.setObjectName("separator")
        layout.addWidget(sep3)

        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

        layout.addStretch(1)

        # Settings button
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setMinimumWidth(70)
        self.settings_btn.setMaximumWidth(100)
        self.settings_btn.setFixedHeight(40)
        self.settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def _on_lookback_changed(self, index: int):
        """Handle lookback combo selection."""
        data = self.lookback_combo.currentData()

        if data == -1:
            from .custom_start_date_dialog import CustomStartDateDialog

            dialog = CustomStartDateDialog(self.theme_manager, parent=self.window())
            if dialog.exec():
                date_str = dialog.get_start_date()
                if date_str:
                    self._custom_start_date = date_str
                    # Update combo text to show the date
                    self.lookback_combo.blockSignals(True)
                    self.lookback_combo.setItemText(index, date_str)
                    self.lookback_combo.blockSignals(False)
                    self._previous_lookback_index = index
                    self.lookback_changed.emit(date_str)
            else:
                # Cancelled: revert to previous selection
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(self._previous_lookback_index)
                self.lookback_combo.blockSignals(False)
            return

        self._custom_start_date = None
        self._previous_lookback_index = index
        label = self.lookback_combo.currentText()
        self.lookback_changed.emit(label)

    def set_active_view(self, index: int):
        """Set active view programmatically."""
        if 0 <= index < len(self._view_buttons):
            self._view_buttons[index].setChecked(True)

    def set_active_lookback(self, lookback: str):
        """Set active lookback programmatically by label text."""
        for i in range(self.lookback_combo.count()):
            if self.lookback_combo.itemText(i) == lookback:
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(i)
                self._previous_lookback_index = i
                self.lookback_combo.blockSignals(False)
                return

    def update_info(self, headline=None, date_str=None):
        """Update info bar labels."""
        if headline is not None:
            self.headline_label.setText(f"Headline: {headline:.1f}%")

        from datetime import datetime
        self.updated_label.setText(
            f"Updated: {datetime.now().strftime('%m/%d %I:%M%p').lower()}"
        )

    def _apply_theme(self):
        """Apply theme-specific styling."""
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if self.theme_manager.current_theme == "dark":
            bg_hover = "#3d3d3d"
        elif self.theme_manager.current_theme == "light":
            bg_hover = "#e8e8e8"
        else:
            bg_hover = "#1a2838"

        self.setStyleSheet(f"""
            #cpiToolbar {{
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
            #viewTab {{
                background-color: transparent;
                color: {c['text_muted']};
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }}
            #viewTab:hover {{
                background-color: {bg_hover};
                color: {c['text']};
            }}
            #viewTab:checked {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                font-weight: bold;
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
