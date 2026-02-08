"""Rate Probability Toolbar - Home button, info bar, and view tabs."""

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
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from app.services.theme_stylesheet_service import ThemeStylesheetService


class RateProbabilityToolbar(LazyThemeMixin, QWidget):
    """Toolbar with home button, view tabs, info bar, and settings."""

    home_clicked = Signal()
    view_changed = Signal(int)  # 0=FedWatch, 1=Rate Path, 2=Evolution
    settings_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup toolbar layout."""
        self.setObjectName("rateProbToolbar")
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

        # View tab buttons (next to Home)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        view_names = ["FedWatch", "Rate Path", "Evolution"]
        self._view_buttons = []
        for i, name in enumerate(view_names):
            btn = QPushButton(name)
            btn.setObjectName("viewTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumWidth(90)
            btn.setFixedHeight(40)
            if i == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, idx=i: self.view_changed.emit(idx))
            layout.addWidget(btn)
            self.button_group.addButton(btn)
            self._view_buttons.append(btn)

        # Separator
        sep = QLabel("|")
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # Info labels
        self.rate_label = QLabel("Rate: --")
        self.rate_label.setObjectName("info_label")
        layout.addWidget(self.rate_label)

        sep2 = QLabel("|")
        sep2.setObjectName("separator")
        layout.addWidget(sep2)

        self.meeting_label = QLabel("Next FOMC: --")
        self.meeting_label.setObjectName("info_label")
        layout.addWidget(self.meeting_label)

        sep3 = QLabel("|")
        sep3.setObjectName("separator")
        layout.addWidget(sep3)

        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

        layout.addStretch(1)

        # Settings button (right-aligned)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setMinimumWidth(70)
        self.settings_btn.setMaximumWidth(100)
        self.settings_btn.setFixedHeight(40)
        self.settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def set_active_view(self, index: int):
        """Set active view programmatically."""
        if 0 <= index < len(self._view_buttons):
            self._view_buttons[index].setChecked(True)

    def update_info(self, target_rate=None, next_meeting=None, days_until=None):
        """Update info bar labels."""
        if target_rate:
            lower, upper = target_rate
            self.rate_label.setText(f"Rate: {lower:.2f}-{upper:.2f}%")

        if next_meeting:
            meeting_str = next_meeting.strftime("%b %d")
            if days_until is not None:
                self.meeting_label.setText(f"Next FOMC: {meeting_str} (in {days_until}d)")
            else:
                self.meeting_label.setText(f"Next FOMC: {meeting_str}")

        from datetime import datetime
        self.updated_label.setText(f"Updated: {datetime.now().strftime('%m/%d %I:%M%p').lower()}")

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
            #rateProbToolbar {{
                background-color: {c['bg']};
            }}
            QLabel {{
                color: {c['text_muted']};
                font-size: 13px;
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
        """)
