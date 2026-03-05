"""Wage Growth Toolbar — Home, lookback, view toggle, stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class WageGrowthToolbar(FredToolbar):
    """Wage Growth toolbar — view toggle (Raw / YoY %) + stats."""

    view_changed = Signal(str)

    def setup_info_section(self, layout):
        layout.addWidget(self._control_label("View:"))

        self.view_combo = self._combo(items=VIEW_OPTIONS)
        self.view_combo.setCurrentIndex(1)  # Default YoY %
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)

        layout.addWidget(self._sep())

        self.ahe_label = self._info_label("AHE: --")
        layout.addWidget(self.ahe_label)
        layout.addWidget(self._sep())
        self.eci_label = self._info_label("ECI: --")
        layout.addWidget(self.eci_label)
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

    def update_info(self, ahe_yoy=None, eci_yoy=None, ahe_raw=None, **kwargs):
        if ahe_yoy is not None:
            if ahe_raw is not None:
                self.ahe_label.setText(f"AHE: ${ahe_raw:.2f}/hr ({ahe_yoy:+.1f}%)")
            else:
                self.ahe_label.setText(f"AHE: {ahe_yoy:+.1f}%")
        if eci_yoy is not None:
            self.eci_label.setText(f"ECI: {eci_yoy:+.1f}%")
        self._update_timestamp()
