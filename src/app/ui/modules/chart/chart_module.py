from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.price_chart import PriceChart
from app.services.market_data import fetch_price_history
from app.services.ticker_equation_parser import TickerEquationParser
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


class ChartModule(QWidget):
    """
    Charting module - extracted from MainWindow.
    Handles ticker data loading and chart display.
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.equation_parser = TickerEquationParser()
        
        self._setup_ui()
        self._setup_state()
        self._connect_signals()

        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

        # Auto-load initial ticker
        self.load_ticker_max(self.ticker_input.text())

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change signal."""
        self._apply_control_bar_theme()
        self.chart.set_theme(theme)

    def _apply_control_bar_theme(self) -> None:
        """Apply theme-specific styling to the control bar."""
        stylesheet = self.theme_manager.get_controls_stylesheet()
        self.controls_widget.setStyleSheet(stylesheet)

    def _setup_ui(self) -> None:
        """Create the UI layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Controls bar with better styling
        self.controls_widget = QWidget()
        
        controls = QHBoxLayout(self.controls_widget)
        controls.setContentsMargins(15, 12, 15, 12)
        controls.setSpacing(20)

        # Ticker input
        controls.addWidget(QLabel("TICKER"))
        self.ticker_input = QLineEdit()
        self.ticker_input.setText(DEFAULT_TICKER)
        self.ticker_input.setMaximumWidth(200)
        self.ticker_input.setPlaceholderText("Ticker or =equation...")
        controls.addWidget(self.ticker_input)

        # Separator
        controls.addSpacing(10)

        # Interval selector
        controls.addWidget(QLabel("INTERVAL"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(CHART_INTERVALS)
        self.interval_combo.setCurrentText(DEFAULT_INTERVAL)
        self.interval_combo.setMaximumWidth(100)
        controls.addWidget(self.interval_combo)

        # Chart type selector
        controls.addWidget(QLabel("CHART"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(CHART_TYPES)
        self.chart_type_combo.setCurrentText(DEFAULT_CHART_TYPE)
        self.chart_type_combo.setMaximumWidth(100)
        controls.addWidget(self.chart_type_combo)

        # Scale selector
        controls.addWidget(QLabel("SCALE"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(CHART_SCALES)
        self.scale_combo.setCurrentText(DEFAULT_SCALE)
        self.scale_combo.setMaximumWidth(120)
        controls.addWidget(self.scale_combo)

        controls.addStretch(1)
        root.addWidget(self.controls_widget)

        # Apply initial theme to control bar
        self._apply_control_bar_theme()

        # Chart
        self.chart = PriceChart()
        root.addWidget(self.chart, stretch=1)
        
        # Apply initial theme to chart
        self.chart.set_theme(self.theme_manager.current_theme)

    def _setup_state(self) -> None:
        """Initialize state management."""
        self.state = {"df": None, "ticker": None, "interval": None}

    def _connect_signals(self) -> None:
        """Connect all signals."""
        # Enter in ticker box -> download and render
        self.ticker_input.returnPressed.connect(
            lambda: self.load_ticker_max(self.ticker_input.text())
        )

        # Change chart type / scale -> re-render only (no refetch)
        self.chart_type_combo.currentTextChanged.connect(lambda _: self.render_from_cache())
        self.scale_combo.currentTextChanged.connect(lambda _: self.render_from_cache())

        # Change interval -> MUST refetch because bars change
        self.interval_combo.currentTextChanged.connect(
            lambda _: self.load_ticker_max(self.ticker_input.text())
        )

    def current_chart_type(self) -> str:
        return self.chart_type_combo.currentText()

    def current_interval(self) -> str:
        return self.interval_combo.currentText()

    def current_scale(self) -> str:
        return self.scale_combo.currentText()

    def render_from_cache(self) -> None:
        """Re-render chart from cached data."""
        if self.state["df"] is None or self.state["ticker"] is None:
            return
        try:
            self.chart.set_prices(
                self.state["df"],
                ticker=self.state["ticker"],
                chart_type=self.current_chart_type(),
                scale=self.current_scale(),
            )
        except Exception as e:
            QMessageBox.critical(self, "Render Error", str(e))

    def load_ticker_max(self, ticker: str) -> None:
        """Load max history for a ticker or evaluate an equation."""
        ticker = (ticker or "").strip()
        if not ticker:
            return

        interval = self.current_interval()

        try:
            # Check if this is an equation
            if self.equation_parser.is_equation(ticker):
                # Parse and evaluate equation
                df, description = self.equation_parser.parse_and_evaluate(
                    ticker, period="max", interval=interval
                )
                display_name = description
            else:
                # Regular ticker
                ticker = ticker.upper()
                df = fetch_price_history(ticker, period="max", interval=interval)
                display_name = ticker

            self.state["df"] = df
            self.state["ticker"] = display_name
            self.state["interval"] = interval

            self.render_from_cache()

        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            # Clear the equation parser cache on error
            self.equation_parser.clear_cache()
