"""Module Toolbar Base — Universal toolbar infrastructure for all modules."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from app.services.theme_stylesheet_service import ThemeStylesheetService


class ModuleToolbar(LazyThemeMixin, QWidget):
    """
    Universal base toolbar for all Quant Terminal modules.

    Provides: Home button | [setup_center content] | stretch | Settings button
    Plus centralized theme stylesheet and lazy theme updates.

    Subclasses MUST implement:
        setup_center(layout) — add module-specific widgets between Home and Settings

    Subclasses MAY override:
        has_settings_button() → bool — default True
        get_extra_stylesheet() → str — default "" (appended after base CSS)
    """

    home_clicked = Signal()
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

    # ── Configuration hooks (override in subclass) ────────────────────────

    def setup_center(self, layout: QHBoxLayout):
        """Add module-specific widgets to the toolbar layout.

        Called between the Home button and the stretch/Settings button.
        """
        pass

    def has_settings_button(self) -> bool:
        """Whether to show a Settings button on the right."""
        return True

    def get_extra_stylesheet(self) -> str:
        """Return extra CSS rules to append to the base toolbar stylesheet."""
        return ""

    # ── UI Setup ──────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setObjectName("moduleToolbar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Home button
        self.home_btn = QPushButton("Home")
        self.home_btn.setMinimumWidth(70)
        self.home_btn.setMaximumWidth(100)
        self.home_btn.setFixedHeight(40)
        self.home_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        # Module-specific center content
        self.setup_center(layout)

        layout.addStretch(1)

        # Settings button
        if self.has_settings_button():
            self.settings_btn = QPushButton("Settings")
            self.settings_btn.setMinimumWidth(70)
            self.settings_btn.setMaximumWidth(100)
            self.settings_btn.setFixedHeight(40)
            self.settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.settings_btn.clicked.connect(self.settings_clicked.emit)
            layout.addWidget(self.settings_btn)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _sep(self) -> QLabel:
        """Create a separator label."""
        s = QLabel("|")
        s.setObjectName("separator")
        return s

    def _info_label(self, text: str = "", object_name: str = "info_label") -> QLabel:
        """Create a themed info label."""
        lbl = QLabel(text)
        lbl.setObjectName(object_name)
        return lbl

    def _control_label(self, text: str) -> QLabel:
        """Create a label for labeling controls (e.g. 'Lookback:')."""
        lbl = QLabel(text)
        lbl.setObjectName("control_label")
        return lbl

    def _combo(self, items=None, min_width: int = 90, max_width: int = 130, height: int = 40):
        """Create a sized NoScrollComboBox with optional items."""
        from app.ui.widgets.common import NoScrollComboBox

        cb = NoScrollComboBox()
        cb.setFixedHeight(height)
        cb.setMinimumWidth(min_width)
        cb.setMaximumWidth(max_width)
        cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if items:
            for item in items:
                cb.addItem(item)
        return cb

    def _update_timestamp(self):
        """Update the 'Updated: ...' label if it exists."""
        if hasattr(self, "updated_label"):
            from datetime import datetime
            self.updated_label.setText(
                f"Updated: {datetime.now().strftime('%m/%d %I:%M%p').lower()}"
            )

    # ── Theme ─────────────────────────────────────────────────────────────

    def _apply_theme(self):
        css = ThemeStylesheetService.get_toolbar_stylesheet(
            self.theme_manager.current_theme
        )
        extra = self.get_extra_stylesheet()
        if extra:
            css += extra
        self.setStyleSheet(css)
