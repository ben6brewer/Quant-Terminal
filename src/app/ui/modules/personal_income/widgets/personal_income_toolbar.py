"""Personal Income Toolbar — Home, lookback, view toggle, data toggle, stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]
DATA_OPTIONS = ["Nominal", "Real"]


class PersonalIncomeToolbar(FredToolbar):
    """Personal Income toolbar — view + data toggle + stats."""

    view_changed = Signal(str)
    data_mode_changed = Signal(str)

    def setup_info_section(self, layout):
        layout.addWidget(self._control_label("View:"))
        self.view_combo = self._combo(items=VIEW_OPTIONS)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)
        layout.addWidget(self._sep())

        layout.addWidget(self._control_label("Data:"))
        self.data_combo = self._combo(items=DATA_OPTIONS)
        self.data_combo.setCurrentIndex(0)
        self.data_combo.currentIndexChanged.connect(
            lambda _: self.data_mode_changed.emit(self.data_combo.currentText())
        )
        layout.addWidget(self.data_combo)
        layout.addWidget(self._sep())

        self.income_label = self._info_label("PI: --")
        layout.addWidget(self.income_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def set_active_view(self, view: str):
        for i in range(self.view_combo.count()):
            if self.view_combo.itemText(i) == view:
                self.view_combo.blockSignals(True)
                self.view_combo.setCurrentIndex(i)
                self.view_combo.blockSignals(False)
                return

    def set_active_data_mode(self, mode: str):
        for i in range(self.data_combo.count()):
            if self.data_combo.itemText(i) == mode:
                self.data_combo.blockSignals(True)
                self.data_combo.setCurrentIndex(i)
                self.data_combo.blockSignals(False)
                return

    def update_info(self, personal_income=None, **kwargs):
        if personal_income is not None:
            self.income_label.setText(f"PI: ${personal_income:.2f}T")
        self._update_timestamp()
