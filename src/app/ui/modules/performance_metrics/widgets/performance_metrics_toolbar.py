"""Performance Metrics Toolbar - Top Control Bar."""

from typing import List

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import PortfolioTickerComboBox, BenchmarkComboBox
from app.ui.modules.module_toolbar import ModuleToolbar


class PerformanceMetricsToolbar(ModuleToolbar):
    """Toolbar: Home | stretch | Portfolio | Benchmark | stretch | Settings."""

    portfolio_changed = Signal(str)
    benchmark_changed = Signal(str)

    def setup_center(self, layout: QHBoxLayout):
        layout.addStretch(1)

        # Portfolio selector
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

        layout.addSpacing(10)

        # Benchmark selector
        self.benchmark_label = QLabel("Benchmark:")
        self.benchmark_label.setObjectName("control_label")
        layout.addWidget(self.benchmark_label)
        self.benchmark_combo = BenchmarkComboBox()
        self.benchmark_combo.setMinimumWidth(140)
        self.benchmark_combo.setMaximumWidth(250)
        self.benchmark_combo.setFixedHeight(40)
        self.benchmark_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.benchmark_combo.value_changed.connect(self.benchmark_changed.emit)
        layout.addWidget(self.benchmark_combo)

    def update_portfolio_list(self, portfolios: List[str], current: str = None):
        self.portfolio_combo.set_portfolios(portfolios, current)

    def update_benchmark_list(self, portfolios: List[str]):
        self.benchmark_combo.set_portfolios(portfolios)

    def get_current_portfolio(self) -> str:
        return self.portfolio_combo.get_value()

    def get_current_benchmark(self) -> str:
        return self.benchmark_combo.get_value()

    def reset_benchmark(self):
        self.benchmark_combo.reset()
