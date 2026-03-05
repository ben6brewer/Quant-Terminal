"""Analysis Toolbar - Shared top control bar for analysis modules."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy
from PySide6.QtCore import Signal
from PySide6.QtGui import QDoubleValidator

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import NoScrollComboBox
from app.ui.modules.module_toolbar import ModuleToolbar


# Lookback options: label -> calendar days (None = max, -1 = custom)
LOOKBACK_OPTIONS = [
    ("1 Year", 365),
    ("2 Years", 730),
    ("5 Years", 1825),
    ("Max", None),
    ("Custom", -1),
]

# Periodicity options: label -> value
PERIODICITY_OPTIONS = [
    ("Daily", "daily"),
    ("Weekly", "weekly"),
    ("Monthly", "monthly"),
    ("Quarterly", "quarterly"),
    ("Yearly", "yearly"),
]

# Simulation count options
SIMULATION_OPTIONS = [1000, 5000, 10000, 25000, 50000]


class AnalysisToolbar(ModuleToolbar):
    """Shared toolbar for Efficient Frontier, Correlation, and Covariance modules."""

    lookback_changed = Signal(int)
    periodicity_changed = Signal(str)
    simulations_changed = Signal(int)
    risk_aversion_changed = Signal(float)
    run_clicked = Signal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        show_simulations: bool = False,
        show_risk_aversion: bool = False,
        show_periodicity: bool = False,
        run_label: str = "Run",
        parent=None,
    ):
        self._show_simulations = show_simulations
        self._show_risk_aversion = show_risk_aversion
        self._show_periodicity = show_periodicity
        self._custom_date_range = None
        self._previous_lookback_index = 2  # Default: 5 Years
        self._run_label = run_label
        super().__init__(theme_manager, parent)

    def setup_center(self, layout: QHBoxLayout):
        layout.addStretch(1)

        # Lookback selector
        self.lookback_label = QLabel("Lookback:")
        self.lookback_label.setObjectName("control_label")
        layout.addWidget(self.lookback_label)
        self.lookback_combo = NoScrollComboBox()
        self.lookback_combo.setMinimumWidth(85)
        self.lookback_combo.setMaximumWidth(120)
        self.lookback_combo.setFixedHeight(40)
        self.lookback_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, days in LOOKBACK_OPTIONS:
            self.lookback_combo.addItem(label, days)
        self.lookback_combo.setCurrentIndex(2)  # Default: 5 Years
        self.lookback_combo.currentIndexChanged.connect(self._on_lookback_changed)
        layout.addWidget(self.lookback_combo)

        # Periodicity selector
        if self._show_periodicity:
            layout.addSpacing(8)

            self.periodicity_label = QLabel("Periodicity:")
            self.periodicity_label.setObjectName("control_label")
            layout.addWidget(self.periodicity_label)
            self.periodicity_combo = NoScrollComboBox()
            self.periodicity_combo.setMinimumWidth(85)
            self.periodicity_combo.setMaximumWidth(120)
            self.periodicity_combo.setFixedHeight(40)
            self.periodicity_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            for label, value in PERIODICITY_OPTIONS:
                self.periodicity_combo.addItem(label, value)
            self.periodicity_combo.setCurrentIndex(0)
            self.periodicity_combo.currentIndexChanged.connect(self._on_periodicity_changed)
            layout.addWidget(self.periodicity_combo)

        # Simulations selector
        if self._show_simulations:
            layout.addSpacing(8)

            self.sims_label = QLabel("Simulations:")
            self.sims_label.setObjectName("control_label")
            layout.addWidget(self.sims_label)
            self.sims_combo = NoScrollComboBox()
            self.sims_combo.setMinimumWidth(80)
            self.sims_combo.setMaximumWidth(110)
            self.sims_combo.setFixedHeight(40)
            self.sims_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            for count in SIMULATION_OPTIONS:
                self.sims_combo.addItem(f"{count:,}", count)
            self.sims_combo.setCurrentIndex(2)  # Default: 10,000
            self.sims_combo.currentIndexChanged.connect(self._on_sims_changed)
            layout.addWidget(self.sims_combo)

        # Risk aversion input
        if self._show_risk_aversion:
            layout.addSpacing(8)

            self.gamma_label = QLabel("Risk Aversion:")
            self.gamma_label.setObjectName("control_label")
            layout.addWidget(self.gamma_label)

            self.gamma_input = QLineEdit()
            self.gamma_input.setPlaceholderText("e.g. 2.0")
            self.gamma_input.setFixedWidth(70)
            self.gamma_input.setFixedHeight(40)
            self.gamma_input.setValidator(QDoubleValidator(0.01, 100.0, 2))
            self.gamma_input.editingFinished.connect(self._on_gamma_changed)
            layout.addWidget(self.gamma_input)

        layout.addSpacing(8)

        # Run button
        self.run_btn = QPushButton(self._run_label)
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
                self.lookback_changed.emit(-1)
            else:
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(self._previous_lookback_index)
                self.lookback_combo.blockSignals(False)
            return

        self._custom_date_range = None
        self._previous_lookback_index = index
        self.lookback_changed.emit(data if data is not None else 0)

    def _on_gamma_changed(self):
        if not self._show_risk_aversion:
            return
        text = self.gamma_input.text().strip()
        if text:
            try:
                self.risk_aversion_changed.emit(float(text))
            except ValueError:
                pass
        else:
            self.risk_aversion_changed.emit(0.0)

    def _on_periodicity_changed(self, index: int):
        value = self.periodicity_combo.currentData()
        if value:
            self.periodicity_changed.emit(value)

    def _on_sims_changed(self, index: int):
        count = self.sims_combo.currentData()
        if count:
            self.simulations_changed.emit(count)

    def set_lookback(self, days: int):
        for i in range(self.lookback_combo.count()):
            data = self.lookback_combo.itemData(i)
            if data == days or (days == 0 and data is None):
                self.lookback_combo.setCurrentIndex(i)
                return

    def set_simulations(self, count: int):
        if not self._show_simulations:
            return
        for i in range(self.sims_combo.count()):
            if self.sims_combo.itemData(i) == count:
                self.sims_combo.setCurrentIndex(i)
                return

    def get_periodicity(self) -> str:
        if not self._show_periodicity:
            return "daily"
        return self.periodicity_combo.currentData() or "daily"

    def set_periodicity(self, value: str):
        if not self._show_periodicity:
            return
        for i in range(self.periodicity_combo.count()):
            if self.periodicity_combo.itemData(i) == value:
                self.periodicity_combo.setCurrentIndex(i)
                return

    def get_risk_aversion(self) -> float:
        if not self._show_risk_aversion:
            return 0.0
        text = self.gamma_input.text().strip()
        if text:
            try:
                return float(text)
            except ValueError:
                pass
        return 0.0

    @property
    def custom_date_range(self):
        return self._custom_date_range
