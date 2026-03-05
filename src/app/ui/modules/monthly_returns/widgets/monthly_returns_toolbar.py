"""Monthly Returns Toolbar - Top Control Bar."""

from typing import List

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import PortfolioTickerComboBox
from app.ui.modules.module_toolbar import ModuleToolbar


class MonthlyReturnsToolbar(ModuleToolbar):
    """Toolbar for Monthly Returns module: Home + Portfolio/Ticker selector."""

    portfolio_changed = Signal(str)

    def setup_center(self, layout: QHBoxLayout):
        layout.addStretch(1)

        self.portfolio_label = QLabel("Portfolio:")
        self.portfolio_label.setObjectName("control_label")
        layout.addWidget(self.portfolio_label)
        self.portfolio_combo = PortfolioTickerComboBox()
        self.portfolio_combo.setMinimumWidth(140)
        self.portfolio_combo.setMaximumWidth(250)
        self.portfolio_combo.setFixedHeight(40)
        self.portfolio_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.portfolio_combo.value_changed.connect(self.portfolio_changed.emit)
        layout.addWidget(self.portfolio_combo)

    def update_portfolio_list(self, portfolios: List[str], current: str = None):
        self.portfolio_combo.set_portfolios(portfolios, current)

    def set_ticker_text(self, ticker: str):
        self.portfolio_combo.lineEdit().setText(ticker)
