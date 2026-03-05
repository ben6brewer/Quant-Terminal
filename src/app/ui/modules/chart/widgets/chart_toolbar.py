"""Chart Toolbar - Control bar for chart module."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QSizePolicy
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.core.config import (
    DEFAULT_TICKER,
    DEFAULT_INTERVAL,
    DEFAULT_CHART_TYPE,
    DEFAULT_SCALE,
    CHART_INTERVALS,
    CHART_TYPES,
    CHART_SCALES,
)
from app.ui.modules.module_toolbar import ModuleToolbar


class ChartToolbar(ModuleToolbar):
    """Control bar for chart configuration."""

    ticker_changed = Signal(str)
    interval_changed = Signal(str)
    chart_type_changed = Signal(str)
    scale_changed = Signal(str)
    indicators_toggled = Signal(bool)
    depth_toggled = Signal(bool)

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)
        self._connect_signals()

    def setup_center(self, layout: QHBoxLayout):
        layout.addStretch(1)

        # Ticker input
        self.ticker_label = QLabel("Ticker:")
        self.ticker_label.setObjectName("control_label")
        layout.addWidget(self.ticker_label)
        self.ticker_input = QLineEdit()
        self.ticker_input.setText(DEFAULT_TICKER)
        self.ticker_input.setMinimumWidth(120)
        self.ticker_input.setMaximumWidth(200)
        self.ticker_input.setFixedHeight(40)
        self.ticker_input.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.ticker_input.setPlaceholderText("Ticker or =equation...")
        self.ticker_input.textEdited.connect(self._on_ticker_text_edited)
        layout.addWidget(self.ticker_input)

        layout.addSpacing(10)

        # Interval selector
        self.interval_label = QLabel("Interval:")
        self.interval_label.setObjectName("control_label")
        layout.addWidget(self.interval_label)
        self.interval_combo = QComboBox()
        self.interval_combo.setMinimumWidth(80)
        self.interval_combo.setMaximumWidth(120)
        self.interval_combo.setFixedHeight(40)
        self.interval_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.interval_combo.addItems(CHART_INTERVALS)
        self.interval_combo.setCurrentText(DEFAULT_INTERVAL)
        layout.addWidget(self.interval_combo)

        layout.addSpacing(10)

        # Chart type selector
        self.chart_type_label = QLabel("Chart:")
        self.chart_type_label.setObjectName("control_label")
        layout.addWidget(self.chart_type_label)
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.setMinimumWidth(80)
        self.chart_type_combo.setMaximumWidth(120)
        self.chart_type_combo.setFixedHeight(40)
        self.chart_type_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.chart_type_combo.addItems(CHART_TYPES)
        self.chart_type_combo.setCurrentText(DEFAULT_CHART_TYPE)
        layout.addWidget(self.chart_type_combo)

        layout.addSpacing(10)

        # Scale selector
        self.scale_label = QLabel("Scale:")
        self.scale_label.setObjectName("control_label")
        layout.addWidget(self.scale_label)
        self.scale_combo = QComboBox()
        self.scale_combo.setMinimumWidth(80)
        self.scale_combo.setMaximumWidth(130)
        self.scale_combo.setFixedHeight(40)
        self.scale_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.scale_combo.addItems(CHART_SCALES)
        self.scale_combo.setCurrentText(DEFAULT_SCALE)
        layout.addWidget(self.scale_combo)

        layout.addSpacing(10)

        # Indicators button
        self.indicators_btn = QPushButton("Indicators")
        self.indicators_btn.setMinimumWidth(70)
        self.indicators_btn.setMaximumWidth(100)
        self.indicators_btn.setFixedHeight(40)
        self.indicators_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.indicators_btn.setCheckable(True)
        layout.addWidget(self.indicators_btn)

        # Depth button
        self.depth_btn = QPushButton("Depth")
        self.depth_btn.setMinimumWidth(70)
        self.depth_btn.setMaximumWidth(100)
        self.depth_btn.setFixedHeight(40)
        self.depth_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.depth_btn.setCheckable(True)
        self.depth_btn.setEnabled(False)
        layout.addWidget(self.depth_btn)

    def _connect_signals(self):
        self.ticker_input.returnPressed.connect(
            lambda: self.ticker_changed.emit(self.ticker_input.text())
        )
        self.interval_combo.currentTextChanged.connect(self.interval_changed.emit)
        self.chart_type_combo.currentTextChanged.connect(self.chart_type_changed.emit)
        self.scale_combo.currentTextChanged.connect(self.scale_changed.emit)
        self.indicators_btn.clicked.connect(
            lambda: self.indicators_toggled.emit(self.indicators_btn.isChecked())
        )
        self.depth_btn.clicked.connect(
            lambda: self.depth_toggled.emit(self.depth_btn.isChecked())
        )

    def _on_ticker_text_edited(self, text: str):
        cursor_pos = self.ticker_input.cursorPosition()
        self.ticker_input.setText(text.upper())
        self.ticker_input.setCursorPosition(cursor_pos)

    # Public getters/setters
    def get_ticker(self) -> str:
        return self.ticker_input.text()

    def get_interval(self) -> str:
        return self.interval_combo.currentText()

    def get_chart_type(self) -> str:
        return self.chart_type_combo.currentText()

    def get_scale(self) -> str:
        return self.scale_combo.currentText()

    def set_depth_enabled(self, enabled: bool):
        self.depth_btn.setEnabled(enabled)

    def set_depth_visible(self, visible: bool):
        self.depth_btn.setVisible(visible)

    def set_depth_text(self, text: str):
        self.depth_btn.setText(text)

    def set_indicators_checked(self, checked: bool):
        self.indicators_btn.setChecked(checked)

    def set_depth_checked(self, checked: bool):
        self.depth_btn.setChecked(checked)
