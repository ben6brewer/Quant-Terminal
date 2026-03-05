"""Risk Analytics Toolbar - Top Control Bar."""

from typing import List

from PySide6.QtWidgets import QHBoxLayout, QLabel, QComboBox, QPushButton, QSizePolicy
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import PortfolioComboBox
from app.services.ishares_holdings_service import ISharesHoldingsService
from app.ui.modules.module_toolbar import ModuleToolbar


class RiskAnalyticsToolbar(ModuleToolbar):
    """Toolbar: Home | stretch | Portfolio | Benchmark ETF | Analyze | stretch | Settings."""

    portfolio_changed = Signal(str)
    etf_benchmark_changed = Signal(str)
    analyze_clicked = Signal()

    def setup_center(self, layout: QHBoxLayout):
        layout.addStretch(1)

        # Portfolio selector
        self.portfolio_label = QLabel("Portfolio:")
        self.portfolio_label.setObjectName("control_label")
        layout.addWidget(self.portfolio_label)
        self.portfolio_combo = PortfolioComboBox()
        self.portfolio_combo.setMinimumWidth(140)
        self.portfolio_combo.setMaximumWidth(250)
        self.portfolio_combo.setFixedHeight(40)
        self.portfolio_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.portfolio_combo.value_changed.connect(self.portfolio_changed.emit)
        layout.addWidget(self.portfolio_combo)

        layout.addSpacing(10)

        # Benchmark selector (ETF dropdown)
        self.benchmark_label = QLabel("Benchmark:")
        self.benchmark_label.setObjectName("control_label")
        layout.addWidget(self.benchmark_label)
        self.etf_benchmark_combo = QComboBox()
        self.etf_benchmark_combo.addItems(ISharesHoldingsService.get_available_etfs())
        self.etf_benchmark_combo.setMinimumWidth(70)
        self.etf_benchmark_combo.setMaximumWidth(100)
        self.etf_benchmark_combo.setFixedHeight(40)
        self.etf_benchmark_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.etf_benchmark_combo.currentTextChanged.connect(
            self.etf_benchmark_changed.emit
        )
        layout.addWidget(self.etf_benchmark_combo)

        layout.addSpacing(8)

        # Analyze button (uses run_btn styling from base)
        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.setMinimumWidth(70)
        self.analyze_btn.setMaximumWidth(100)
        self.analyze_btn.setFixedHeight(40)
        self.analyze_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.analyze_btn.setObjectName("run_btn")
        self.analyze_btn.clicked.connect(self.analyze_clicked.emit)
        layout.addWidget(self.analyze_btn)

    def update_portfolio_list(self, portfolios: List[str], current: str = None):
        self.portfolio_combo.set_portfolios(portfolios, current)

    def get_current_portfolio(self) -> str:
        return self.portfolio_combo.get_value()

    def get_current_etf_benchmark(self) -> str:
        return self.etf_benchmark_combo.currentText()

    def set_etf_benchmark(self, etf: str):
        index = self.etf_benchmark_combo.findText(etf)
        if index >= 0:
            self.etf_benchmark_combo.setCurrentIndex(index)
