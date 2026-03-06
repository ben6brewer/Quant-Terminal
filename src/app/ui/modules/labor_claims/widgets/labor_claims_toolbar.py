"""Labor Claims Toolbar - Home, lookback, view toggle, claims info, settings."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class LaborClaimsToolbar(FredToolbar):
    """Labor Claims toolbar — view toggle (Raw / YoY %) + latest claims reading."""

    view_changed = Signal(str)

    def supports_custom_date(self):
        return True

    def setup_info_section(self, layout):
        layout.addWidget(self._control_label("View:"))

        self.view_combo = self._combo(items=VIEW_OPTIONS)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)

        layout.addWidget(self._sep())

        self.claims_label = self._info_label("Claims: --")
        layout.addWidget(self.claims_label)
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

    def update_info(self, claims=None, **kwargs):
        if claims is not None:
            self.claims_label.setText(f"Claims: {claims:,.0f}")
        self._update_timestamp()
