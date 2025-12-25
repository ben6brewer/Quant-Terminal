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

from app.widgets.price_chart import PriceChart
from app.services.market_data import fetch_price_history
from app.services.ticker_equation_parser import TickerEquationParser


class ChartModule(QWidget):
    """
    Charting module - extracted from MainWindow.
    Handles ticker data loading and chart display.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_theme = "dark"
        self.equation_parser = TickerEquationParser()
        self._setup_ui()
        self._setup_state()
        self._connect_signals()

        # Auto-load initial ticker
        self.load_ticker_max(self.ticker_input.text())

    def set_theme(self, theme: str) -> None:
        """Update the chart module theme."""
        self.current_theme = theme
        self._apply_control_bar_theme()
        self._apply_chart_theme()

    def _apply_chart_theme(self) -> None:
        """Apply theme to the chart widget."""
        if self.current_theme == "light":
            self.chart.setBackground('w')  # white background
        else:
            self.chart.setBackground('#1e1e1e')  # dark background

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
        self.ticker_input.setText("BTC-USD")
        self.ticker_input.setMaximumWidth(200)
        self.ticker_input.setPlaceholderText("Ticker or =equation...")
        controls.addWidget(self.ticker_input)

        # Separator
        controls.addSpacing(10)

        # Interval selector
        controls.addWidget(QLabel("INTERVAL"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["daily", "weekly", "monthly", "yearly"])
        self.interval_combo.setCurrentText("daily")
        self.interval_combo.setMaximumWidth(100)
        controls.addWidget(self.interval_combo)

        # Chart type selector
        controls.addWidget(QLabel("CHART"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["Candles", "Line"])
        self.chart_type_combo.setCurrentText("Candles")
        self.chart_type_combo.setMaximumWidth(100)
        controls.addWidget(self.chart_type_combo)

        # Scale selector
        controls.addWidget(QLabel("SCALE"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["Regular", "Logarithmic"])
        self.scale_combo.setCurrentText("Logarithmic")
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
        self._apply_chart_theme()

    def _setup_state(self) -> None:
        """Initialize state management."""
        self.state = {"df": None, "ticker": None, "interval": None}

    def _apply_control_bar_theme(self) -> None:
        """Apply theme-specific styling to the control bar."""
        if self.current_theme == "light":
            stylesheet = """
                QWidget {
                    background-color: #f5f5f5;
                    border-bottom: 2px solid #0066cc;
                }
                QLabel {
                    color: #333333;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0px 5px;
                }
                QLineEdit {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    padding: 8px 12px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QLineEdit:focus {
                    border: 1px solid #0066cc;
                }
                QComboBox {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    padding: 8px 12px;
                    font-size: 13px;
                }
                QComboBox:hover {
                    border: 1px solid #0066cc;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #333333;
                    margin-right: 5px;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #000000;
                    selection-background-color: #0066cc;
                    selection-color: #ffffff;
                    border: 1px solid #d0d0d0;
                }
            """
        else:  # dark theme
            stylesheet = """
                QWidget {
                    background-color: #2d2d2d;
                    border-bottom: 2px solid #00d4ff;
                }
                QLabel {
                    color: #cccccc;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0px 5px;
                }
                QLineEdit {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 8px 12px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QLineEdit:focus {
                    border: 1px solid #00d4ff;
                }
                QComboBox {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 8px 12px;
                    font-size: 13px;
                }
                QComboBox:hover {
                    border: 1px solid #00d4ff;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #cccccc;
                    margin-right: 5px;
                }
                QComboBox QAbstractItemView {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    selection-background-color: #00d4ff;
                    selection-color: #000000;
                    border: 1px solid #3d3d3d;
                }
            """
        
        self.controls_widget.setStyleSheet(stylesheet)

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