"""Bank Lending Toolbar — Home, lookback, view toggle, stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class BankLendingToolbar(FredToolbar):
    """Bank Lending toolbar — view toggle (Raw / YoY %) + total loans stat."""

    view_changed = Signal(str)

    def get_default_lookback_index(self) -> int:
        return 3  # 10Y

    def setup_info_section(self, layout):
        layout.addWidget(self._control_label("View:"))

        self.view_combo = self._combo(items=VIEW_OPTIONS)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)

        layout.addWidget(self._sep())

        self.total_label = self._info_label("Total: --")
        layout.addWidget(self.total_label)
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

    def update_info(self, total_loans=None, **kwargs):
        if total_loans is not None:
            self.total_label.setText(f"Total: ${total_loans:,.0f}B")
        self._update_timestamp()
