"""Government Debt Toolbar — Home, lookback, view toggle, stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "% GDP", "YoY", "Debt/GDP YoY"]


class GovernmentDebtToolbar(FredToolbar):
    """Government Debt toolbar — view toggle + stats."""

    view_changed = Signal(str)

    def get_lookback_options(self):
        return ["5Y", "10Y", "20Y", "Max"]

    def get_default_lookback_index(self) -> int:
        return 3  # Max

    def setup_info_section(self, layout):
        layout.addWidget(self._control_label("View:"))
        self.view_combo = self._combo(items=VIEW_OPTIONS)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)
        layout.addWidget(self._sep())

        self.debt_label = self._info_label("Debt: --")
        layout.addWidget(self.debt_label)
        layout.addWidget(self._sep())
        self.gdp_label = self._info_label("Debt/GDP: --")
        layout.addWidget(self.gdp_label)
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

    def update_info(self, debt_trillions=None, debt_gdp_pct=None, **kwargs):
        if debt_trillions is not None:
            self.debt_label.setText(f"Debt: ${debt_trillions:.1f}T")
        if debt_gdp_pct is not None:
            self.gdp_label.setText(f"Debt/GDP: {debt_gdp_pct:.1f}%")
        self._update_timestamp()
