"""OLS Toolbar - Control bar for OLS Regression module."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import NoScrollComboBox, AutoSelectLineEdit
from app.ui.modules.module_toolbar import ModuleToolbar


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


class OLSToolbar(ModuleToolbar):
    """Toolbar for the OLS Regression module."""

    run_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._custom_date_range = None
        self._previous_lookback_index = 3  # Default: Max
        super().__init__(theme_manager, parent)

    def setup_center(self, layout: QHBoxLayout):
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

    def _on_lookback_changed(self, index: int):
        data = self.lookback_combo.currentData()

        if data == -1:
            from .custom_date_dialog import CustomDateDialog

            dialog = CustomDateDialog(self.theme_manager, parent=self.window())
            if dialog.exec():
                self._custom_date_range = dialog.get_date_range()
                self._previous_lookback_index = index
            else:
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
