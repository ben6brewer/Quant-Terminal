"""Industrial Production Toolbar — Home, lookback, view toggle, IP Index / Capacity Util stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class IndustrialProductionToolbar(FredToolbar):
    """Industrial Production toolbar — view toggle (Raw / YoY %) + IP Index and Capacity Utilization."""

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

        self.ip_label = self._info_label("IP Index: --")
        layout.addWidget(self.ip_label)
        layout.addWidget(self._sep())
        self.cap_label = self._info_label("Cap. Util: --")
        layout.addWidget(self.cap_label)
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

    def update_info(self, ip_index=None, capacity_util=None, **kwargs):
        if ip_index is not None:
            self.ip_label.setText(f"IP Index: {ip_index:.1f}")
        if capacity_util is not None:
            self.cap_label.setText(f"Cap. Util: {capacity_util:.1f}%")
        self._update_timestamp()
