"""Rolling Toolbar - Control bar for rolling correlation/covariance modules."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import NoScrollComboBox, AutoSelectLineEdit
from app.ui.modules.module_toolbar import ModuleToolbar


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


class RollingToolbar(ModuleToolbar):
    """Toolbar for Rolling Correlation and Rolling Covariance modules."""

    run_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, mode: str = "correlation", parent=None):
        self._mode = mode
        self._custom_date_range = None
        self._custom_window_days = None
        self._previous_lookback_index = 3  # Default: Max
        self._previous_window_index = 1    # Default: 3M
        super().__init__(theme_manager, parent)

    def setup_center(self, layout: QHBoxLayout):
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
        self.window_combo.setCurrentIndex(1)  # Default: 3M
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

    def _on_window_changed(self, index: int):
        data = self.window_combo.currentData()

        if data == -1:
            from .custom_window_dialog import CustomWindowDialog

            dialog = CustomWindowDialog(self.theme_manager, parent=self.window())
            if dialog.exec():
                years = dialog.get_years()
                if years is not None:
                    self._custom_window_days = int(round(years * 252))
                    self.window_combo.blockSignals(True)
                    self.window_combo.setItemText(index, f"{years:.2f}Y")
                    self.window_combo.setItemData(index, self._custom_window_days)
                    self.window_combo.blockSignals(False)
                    self._previous_window_index = index
            else:
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
        data = self.window_combo.currentData()
        if data and data > 0:
            return data
        if self._custom_window_days:
            return self._custom_window_days
        return 63

    @property
    def custom_date_range(self):
        return self._custom_date_range

    def set_tickers(self, t1: str, t2: str):
        self.ticker1_input.setText(t1)
        self.ticker2_input.setText(t2)

    def set_rolling_window(self, days: int):
        for i in range(self.window_combo.count()):
            data = self.window_combo.itemData(i)
            if data == days:
                self.window_combo.setCurrentIndex(i)
                return

    def set_lookback(self, days):
        for i in range(self.lookback_combo.count()):
            data = self.lookback_combo.itemData(i)
            if data == days or (days is None and data is None):
                self.lookback_combo.setCurrentIndex(i)
                return
