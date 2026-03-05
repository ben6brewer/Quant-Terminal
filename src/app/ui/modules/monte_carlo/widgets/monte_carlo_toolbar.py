"""Monte Carlo Toolbar - Top Control Bar for Monte Carlo module."""

from typing import List, Optional
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Signal, QDate

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import NoScrollComboBox, PortfolioTickerComboBox, BenchmarkComboBox
from app.ui.modules.module_toolbar import ModuleToolbar
from .monte_carlo_controls import HorizonComboBox, CustomHorizonDialog


class MonteCarloToolbar(ModuleToolbar):
    """Toolbar for Monte Carlo simulation module."""

    portfolio_changed = Signal(str)
    method_changed = Signal(str)
    horizon_changed = Signal(int)
    simulations_changed = Signal(int)
    benchmark_changed = Signal(str)
    run_simulation = Signal()

    CUSTOM_HORIZON_TEXT = "Custom"
    METHOD_OPTIONS = ["Bootstrap", "Parametric"]
    METHOD_MAP = {"Bootstrap": "bootstrap", "Parametric": "parametric"}
    METHOD_REVERSE = {v: k for k, v in METHOD_MAP.items()}
    HORIZON_OPTIONS = [1, 2, 3, 5, 10]
    SIMULATION_OPTIONS = [100, 500, 1000, 5000, 10000]

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

        layout.addSpacing(10)

        # Method selector
        self.method_label = QLabel("Method:")
        self.method_label.setObjectName("control_label")
        layout.addWidget(self.method_label)
        self.method_combo = NoScrollComboBox()
        self.method_combo.setMinimumWidth(85)
        self.method_combo.setMaximumWidth(120)
        self.method_combo.setFixedHeight(40)
        self.method_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.method_combo.addItems(self.METHOD_OPTIONS)
        self.method_combo.currentTextChanged.connect(self._on_method_changed)
        layout.addWidget(self.method_combo)

        layout.addSpacing(8)

        # Time horizon selector
        self.horizon_label = QLabel("Horizon:")
        self.horizon_label.setObjectName("control_label")
        layout.addWidget(self.horizon_label)
        self.horizon_combo = HorizonComboBox()
        self.horizon_combo.setMinimumWidth(85)
        self.horizon_combo.setMaximumWidth(125)
        self.horizon_combo.setFixedHeight(40)
        self.horizon_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for years in self.HORIZON_OPTIONS:
            self.horizon_combo.addItem(f"{years} Year{'s' if years > 1 else ''}", years)
        self.horizon_combo.addItem(self.CUSTOM_HORIZON_TEXT, -1)
        self.horizon_combo.currentIndexChanged.connect(self._on_horizon_changed)
        layout.addWidget(self.horizon_combo)
        self._custom_horizon_days: Optional[int] = None

        layout.addSpacing(8)

        # Simulations selector
        self.sims_label = QLabel("Simulations:")
        self.sims_label.setObjectName("control_label")
        layout.addWidget(self.sims_label)
        self.sims_combo = NoScrollComboBox()
        self.sims_combo.setMinimumWidth(70)
        self.sims_combo.setMaximumWidth(100)
        self.sims_combo.setFixedHeight(40)
        self.sims_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for count in self.SIMULATION_OPTIONS:
            self.sims_combo.addItem(f"{count:,}", count)
        self.sims_combo.setCurrentIndex(2)  # Default 1000
        self.sims_combo.currentIndexChanged.connect(self._on_sims_changed)
        layout.addWidget(self.sims_combo)

        layout.addSpacing(8)

        # Run button
        self.run_btn = QPushButton("Run Simulation")
        self.run_btn.setMinimumWidth(90)
        self.run_btn.setMaximumWidth(140)
        self.run_btn.setFixedHeight(40)
        self.run_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.run_btn.setObjectName("run_btn")
        self.run_btn.clicked.connect(self.run_simulation.emit)
        layout.addWidget(self.run_btn)

    def _on_method_changed(self, text: str):
        method = self.METHOD_MAP.get(text, "bootstrap")
        self.method_changed.emit(method)

    def _on_horizon_changed(self, index: int):
        data = self.horizon_combo.currentData()

        if data == -1:
            self._show_custom_horizon_dialog()
        elif data:
            trading_days = data * 252
            self.horizon_combo.clear_custom_years()
            self.horizon_changed.emit(trading_days)

    def _show_custom_horizon_dialog(self):
        dialog = CustomHorizonDialog(self.theme_manager, self)
        if dialog.exec():
            end_date = dialog.get_end_date()
            if end_date:
                today = QDate.currentDate()
                calendar_days = today.daysTo(end_date)
                trading_days = int(calendar_days * 252 / 365)
                trading_days = max(1, trading_days)
                self._custom_horizon_days = trading_days
                years = trading_days / 252
                self.horizon_combo.set_custom_years(years)
                self.horizon_changed.emit(trading_days)
        else:
            self.horizon_combo.clear_custom_years()
            self.horizon_combo.blockSignals(True)
            self.horizon_combo.setCurrentIndex(0)
            self.horizon_combo.blockSignals(False)

    def _on_sims_changed(self, index: int):
        count = self.sims_combo.currentData()
        if count:
            self.simulations_changed.emit(count)

    def set_portfolio_list(self, portfolios: List[str]):
        self.portfolio_combo.set_portfolios(portfolios)

    def set_benchmark_list(self, portfolios: List[str]):
        self.benchmark_combo.set_portfolios(portfolios)

    def set_method(self, method: str):
        display = self.METHOD_REVERSE.get(method, "Bootstrap")
        self.method_combo.setCurrentText(display)

    def set_horizon(self, years: int):
        for i in range(self.horizon_combo.count()):
            if self.horizon_combo.itemData(i) == years:
                self.horizon_combo.setCurrentIndex(i)
                break

    def set_simulations(self, count: int):
        for i in range(self.sims_combo.count()):
            if self.sims_combo.itemData(i) == count:
                self.sims_combo.setCurrentIndex(i)
                break

    def get_current_portfolio(self) -> str:
        return self.portfolio_combo.get_value()

    def get_current_benchmark(self) -> str:
        return self.benchmark_combo.get_value()

    def get_current_method(self) -> str:
        return self.METHOD_MAP.get(self.method_combo.currentText(), "bootstrap")

    def get_current_horizon(self) -> int:
        return self.horizon_combo.currentData() or 1

    def get_current_simulations(self) -> int:
        return self.sims_combo.currentData() or 1000
