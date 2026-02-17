"""Rolling Controls Widget - Control bar for rolling correlation/covariance modules."""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import (
    LazyThemeMixin,
    NoScrollComboBox,
    AutoSelectLineEdit,
)
from app.services.theme_stylesheet_service import ThemeStylesheetService


# Rolling window options: label -> trading days (-1 = custom)
WINDOW_OPTIONS = [
    ("1M", 21),
    ("3M", 63),
    ("6M", 126),
    ("1Y", 252),
    ("2Y", 504),
    ("Custom", -1),
]

# Lookback options: label -> calendar days (None = max, -1 = custom)
LOOKBACK_OPTIONS = [
    ("1 Year", 365),
    ("2 Years", 730),
    ("5 Years", 1825),
    ("Max", None),
    ("Custom", -1),
]


class RollingControls(LazyThemeMixin, QWidget):
    """Control bar for Rolling Correlation and Rolling Covariance modules.

    Signals:
        home_clicked: Home button pressed
        run_clicked: Run button pressed
        settings_clicked: Settings button pressed
    """

    home_clicked = Signal()
    run_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, mode: str = "correlation", parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._mode = mode
        self._custom_date_range = None
        self._custom_window_days = None
        self._previous_lookback_index = 3  # Default: Max
        self._previous_window_index = 1    # Default: 3M

        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Home button
        self.home_btn = QPushButton("Home")
        self.home_btn.setMinimumWidth(70)
        self.home_btn.setMaximumWidth(100)
        self.home_btn.setFixedHeight(40)
        self.home_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.home_btn.setObjectName("home_btn")
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        layout.addStretch(1)

        # Ticker 1 input
        t1_label = QLabel("Ticker 1:")
        t1_label.setObjectName("control_label")
        layout.addWidget(t1_label)
        self.ticker1_input = AutoSelectLineEdit()
        self.ticker1_input.setPlaceholderText("e.g. AAPL")
        self.ticker1_input.setMinimumWidth(80)
        self.ticker1_input.setMaximumWidth(120)
        self.ticker1_input.setFixedHeight(40)
        self.ticker1_input.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.ticker1_input)

        layout.addSpacing(8)

        # Ticker 2 input
        t2_label = QLabel("Ticker 2:")
        t2_label.setObjectName("control_label")
        layout.addWidget(t2_label)
        self.ticker2_input = AutoSelectLineEdit()
        self.ticker2_input.setPlaceholderText("e.g. MSFT")
        self.ticker2_input.setMinimumWidth(80)
        self.ticker2_input.setMaximumWidth(120)
        self.ticker2_input.setFixedHeight(40)
        self.ticker2_input.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.ticker2_input)

        layout.addSpacing(8)

        # Rolling window combo
        window_label = QLabel("Window:")
        window_label.setObjectName("control_label")
        layout.addWidget(window_label)
        self.window_combo = NoScrollComboBox()
        self.window_combo.setMinimumWidth(85)
        self.window_combo.setMaximumWidth(120)
        self.window_combo.setFixedHeight(40)
        self.window_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, days in WINDOW_OPTIONS:
            self.window_combo.addItem(label, days)
        self.window_combo.setCurrentIndex(1)  # Default: 3M (63 days)
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        layout.addWidget(self.window_combo)

        layout.addSpacing(8)

        # Lookback combo
        lookback_label = QLabel("Lookback:")
        lookback_label.setObjectName("control_label")
        layout.addWidget(lookback_label)
        self.lookback_combo = NoScrollComboBox()
        self.lookback_combo.setMinimumWidth(85)
        self.lookback_combo.setMaximumWidth(120)
        self.lookback_combo.setFixedHeight(40)
        self.lookback_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, days in LOOKBACK_OPTIONS:
            self.lookback_combo.addItem(label, days)
        self.lookback_combo.setCurrentIndex(3)  # Default: Max
        self.lookback_combo.currentIndexChanged.connect(self._on_lookback_changed)
        layout.addWidget(self.lookback_combo)

        layout.addSpacing(8)

        # Run button
        self.run_btn = QPushButton("Run")
        self.run_btn.setMinimumWidth(80)
        self.run_btn.setMaximumWidth(140)
        self.run_btn.setFixedHeight(40)
        self.run_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.run_btn.setObjectName("run_btn")
        self.run_btn.clicked.connect(self.run_clicked.emit)
        layout.addWidget(self.run_btn)

        layout.addStretch(1)

        # Settings button
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setMinimumWidth(70)
        self.settings_btn.setMaximumWidth(100)
        self.settings_btn.setFixedHeight(40)
        self.settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def _on_window_changed(self, index: int):
        data = self.window_combo.currentData()

        if data == -1:
            from .custom_window_dialog import CustomWindowDialog

            dialog = CustomWindowDialog(self.theme_manager, parent=self.window())
            if dialog.exec():
                years = dialog.get_years()
                if years is not None:
                    self._custom_window_days = int(round(years * 252))
                    # Update combo text to show custom value
                    self.window_combo.blockSignals(True)
                    self.window_combo.setItemText(index, f"{years:.2f}Y")
                    self.window_combo.setItemData(index, self._custom_window_days)
                    self.window_combo.blockSignals(False)
                    self._previous_window_index = index
            else:
                # Cancelled: revert to previous selection
                self.window_combo.blockSignals(True)
                self.window_combo.setCurrentIndex(self._previous_window_index)
                self.window_combo.blockSignals(False)
            return

        self._previous_window_index = index

    def _on_lookback_changed(self, index: int):
        data = self.lookback_combo.currentData()

        if data == -1:
            from .custom_date_dialog import CustomDateDialog

            dialog = CustomDateDialog(self.theme_manager, parent=self.window())
            if dialog.exec():
                self._custom_date_range = dialog.get_date_range()
                self._previous_lookback_index = index
            else:
                # Cancelled: revert to previous selection
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(self._previous_lookback_index)
                self.lookback_combo.blockSignals(False)
            return

        self._custom_date_range = None
        self._previous_lookback_index = index

    # ── Public Methods ────────────────────────────────────────────────

    def get_ticker1(self) -> str:
        return self.ticker1_input.text().strip().upper()

    def get_ticker2(self) -> str:
        return self.ticker2_input.text().strip().upper()

    def get_rolling_window(self) -> int:
        """Return rolling window in trading days."""
        data = self.window_combo.currentData()
        if data and data > 0:
            return data
        if self._custom_window_days:
            return self._custom_window_days
        return 63  # fallback

    @property
    def custom_date_range(self):
        """Return (start_iso, end_iso) tuple or None."""
        return self._custom_date_range

    def set_tickers(self, t1: str, t2: str):
        self.ticker1_input.setText(t1)
        self.ticker2_input.setText(t2)

    def set_rolling_window(self, days: int):
        """Set the window combo to match the given days value."""
        for i in range(self.window_combo.count()):
            data = self.window_combo.itemData(i)
            if data == days:
                self.window_combo.setCurrentIndex(i)
                return

    def set_lookback(self, days):
        """Set the lookback combo to match the given days value."""
        for i in range(self.lookback_combo.count()):
            data = self.lookback_combo.itemData(i)
            if data == days or (days is None and data is None):
                self.lookback_combo.setCurrentIndex(i)
                return

    def _apply_theme(self):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if self.theme_manager.current_theme == "dark":
            bg_hover = "#3d3d3d"
            run_hover = "#00bfe6"
            run_pressed = "#00a6c7"
        elif self.theme_manager.current_theme == "light":
            bg_hover = "#e8e8e8"
            run_hover = "#0055aa"
            run_pressed = "#004488"
        else:  # bloomberg
            bg_hover = "#1a2838"
            run_hover = "#e67300"
            run_pressed = "#cc6600"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg']};
                color: {c['text']};
            }}
            QLabel#control_label {{
                color: {c['text']};
                font-size: 14px;
                font-weight: 500;
                background: transparent;
            }}
            QLineEdit {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
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
            QComboBox QAbstractItemView::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
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
            QPushButton#run_btn {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                font-weight: bold;
                border: 1px solid {c['accent']};
            }}
            QPushButton#run_btn:hover {{
                background-color: {run_hover};
                border-color: {run_hover};
            }}
            QPushButton#run_btn:pressed {{
                background-color: {run_pressed};
            }}
        """)
