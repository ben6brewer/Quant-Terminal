"""Credit Conditions Toolbar — Home, lookback, view toggle, stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Delinquency", "Credit Levels"]


class CreditConditionsToolbar(FredToolbar):
    """Credit Conditions toolbar — view toggle + stats."""

    view_changed = Signal(str)

    def get_lookback_options(self):
        return ["5Y", "10Y", "20Y", "Max"]

    def get_default_lookback_index(self) -> int:
        return 1  # 10Y

    def setup_info_section(self, layout):
        layout.addWidget(self._control_label("View:"))
        self.view_combo = self._combo(items=VIEW_OPTIONS)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)
        layout.addWidget(self._sep())

        self.delinq_label = self._info_label("CC Delinq: --")
        layout.addWidget(self.delinq_label)
        layout.addWidget(self._sep())
        self.credit_label = self._info_label("Credit: --")
        layout.addWidget(self.credit_label)
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

    def update_info(self, cc_delinquency=None, total_credit=None, **kwargs):
        if cc_delinquency is not None:
            self.delinq_label.setText(f"CC Delinq: {cc_delinquency:.1f}%")
        if total_credit is not None:
            self.credit_label.setText(f"Credit: ${total_credit:.2f}T")
        self._update_timestamp()
