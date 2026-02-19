"""OLS Controls Widget - Control bar for OLS Regression module."""

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


# Data mode options: label -> internal key
DATA_MODE_OPTIONS = [
    ("Simple Returns", "simple_returns"),
    ("Log Returns", "log_returns"),
    ("Price Levels", "price_levels"),
]

# Frequency options: label -> internal key
FREQUENCY_OPTIONS = [
    ("Daily", "daily"),
    ("Weekly", "weekly"),
    ("Monthly", "monthly"),
    ("Yearly", "yearly"),
]

# Lookback options: label -> calendar days (None = max, -1 = custom)
LOOKBACK_OPTIONS = [
    ("1 Year", 365),
    ("2 Years", 730),
    ("5 Years", 1825),
    ("Max", None),
    ("Custom", -1),
]


class OLSControls(LazyThemeMixin, QWidget):
    """Control bar for the OLS Regression module.

    Signals:
        home_clicked: Home button pressed
        run_clicked: Run button pressed
        settings_clicked: Settings button pressed
    """

    home_clicked = Signal()
    run_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._custom_date_range = None
        self._previous_lookback_index = 3  # Default: Max

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

        # Ticker X input
        tx_label = QLabel("Ticker X:")
        tx_label.setObjectName("control_label")
        layout.addWidget(tx_label)
        self.ticker_x_input = AutoSelectLineEdit()
        self.ticker_x_input.setPlaceholderText("e.g. SPY")
        self.ticker_x_input.setMinimumWidth(80)
        self.ticker_x_input.setMaximumWidth(120)
        self.ticker_x_input.setFixedHeight(40)
        self.ticker_x_input.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.ticker_x_input)

        layout.addSpacing(8)

        # Ticker Y input
        ty_label = QLabel("Ticker Y:")
        ty_label.setObjectName("control_label")
        layout.addWidget(ty_label)
        self.ticker_y_input = AutoSelectLineEdit()
        self.ticker_y_input.setPlaceholderText("e.g. AAPL")
        self.ticker_y_input.setMinimumWidth(80)
        self.ticker_y_input.setMaximumWidth(120)
        self.ticker_y_input.setFixedHeight(40)
        self.ticker_y_input.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.ticker_y_input)

        layout.addSpacing(8)

        # Data mode combo
        data_label = QLabel("Data:")
        data_label.setObjectName("control_label")
        layout.addWidget(data_label)
        self.data_mode_combo = NoScrollComboBox()
        self.data_mode_combo.setMinimumWidth(120)
        self.data_mode_combo.setMaximumWidth(160)
        self.data_mode_combo.setFixedHeight(40)
        self.data_mode_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, key in DATA_MODE_OPTIONS:
            self.data_mode_combo.addItem(label, key)
        self.data_mode_combo.setCurrentIndex(0)
        layout.addWidget(self.data_mode_combo)

        layout.addSpacing(8)

        # Frequency combo
        freq_label = QLabel("Freq:")
        freq_label.setObjectName("control_label")
        layout.addWidget(freq_label)
        self.frequency_combo = NoScrollComboBox()
        self.frequency_combo.setMinimumWidth(85)
        self.frequency_combo.setMaximumWidth(120)
        self.frequency_combo.setFixedHeight(40)
        self.frequency_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, key in FREQUENCY_OPTIONS:
            self.frequency_combo.addItem(label, key)
        self.frequency_combo.setCurrentIndex(0)
        layout.addWidget(self.frequency_combo)

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

    def get_ticker_x(self) -> str:
        return self.ticker_x_input.text().strip().upper()

    def get_ticker_y(self) -> str:
        return self.ticker_y_input.text().strip().upper()

    def get_data_mode(self) -> str:
        return self.data_mode_combo.currentData()

    def get_frequency(self) -> str:
        return self.frequency_combo.currentData()

    @property
    def custom_date_range(self):
        """Return (start_iso, end_iso) tuple or None."""
        return self._custom_date_range

    def set_tickers(self, tx: str, ty: str):
        self.ticker_x_input.setText(tx)
        self.ticker_y_input.setText(ty)

    def set_data_mode(self, mode: str):
        for i in range(self.data_mode_combo.count()):
            if self.data_mode_combo.itemData(i) == mode:
                self.data_mode_combo.setCurrentIndex(i)
                return

    def set_frequency(self, freq: str):
        for i in range(self.frequency_combo.count()):
            if self.frequency_combo.itemData(i) == freq:
                self.frequency_combo.setCurrentIndex(i)
                return

    def set_lookback(self, days):
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
