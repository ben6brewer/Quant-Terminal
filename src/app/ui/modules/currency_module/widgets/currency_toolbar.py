"""Currency Toolbar — Home, lookback, view toggle, stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class CurrencyToolbar(FredToolbar):
    """Currency toolbar — view toggle (Raw / YoY %) + latest values."""

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

        self.dollar_label = self._info_label("DXY: --")
        layout.addWidget(self.dollar_label)
        layout.addWidget(self._sep())
        self.eur_label = self._info_label("EUR: --")
        layout.addWidget(self.eur_label)
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

    def update_info(self, dollar_index=None, eur=None, **kwargs):
        if dollar_index is not None:
            self.dollar_label.setText(f"DXY: {dollar_index:.1f}")
        if eur is not None:
            self.eur_label.setText(f"EUR: {eur:.4f}")
        self._update_timestamp()
