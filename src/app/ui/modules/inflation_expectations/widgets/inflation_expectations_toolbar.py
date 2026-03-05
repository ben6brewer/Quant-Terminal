"""Inflation Expectations Toolbar - Home, lookback, breakeven info, settings."""

from PySide6.QtWidgets import QLabel

from app.ui.modules.fred_toolbar import FredToolbar


class InflationExpectationsToolbar(FredToolbar):
    """Inflation Expectations toolbar — shows latest 5Y Breakeven reading."""

    def get_lookback_options(self):
        return ["1Y", "2Y", "5Y", "10Y", "Max"]

    def setup_info_section(self, layout):
        self.breakeven_label = QLabel("5Y Breakeven: --")
        self.breakeven_label.setObjectName("info_label")
        layout.addWidget(self.breakeven_label)
        layout.addWidget(self._sep())
        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, breakeven_5y=None, **kwargs):
        if breakeven_5y is not None:
            self.breakeven_label.setText(f"5Y Breakeven: {breakeven_5y:.2f}%")
        self._update_timestamp()
