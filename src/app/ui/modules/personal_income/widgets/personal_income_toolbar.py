"""Personal Income Toolbar — Home, lookback, view toggle, stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Income", "Savings"]


class PersonalIncomeToolbar(FredToolbar):
    """Personal Income toolbar — view toggle + stats."""

    view_changed = Signal(str)

    def setup_info_section(self, layout):
        layout.addWidget(self._control_label("View:"))
        self.view_combo = self._combo(items=VIEW_OPTIONS)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)
        layout.addWidget(self._sep())

        self.savings_label = self._info_label("Savings: --")
        layout.addWidget(self.savings_label)
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

    def update_info(self, savings_rate=None, personal_income=None, **kwargs):
        if savings_rate is not None:
            self.savings_label.setText(f"Savings: {savings_rate:.1f}%")
        if personal_income is not None:
            self.income_label.setText(f"PI: ${personal_income:.2f}T")
        self._update_timestamp()
