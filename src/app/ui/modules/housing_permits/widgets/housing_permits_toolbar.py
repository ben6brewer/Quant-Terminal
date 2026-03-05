"""Housing Permits Toolbar — Home, lookback, view toggle (Raw / YoY %), stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class HousingPermitsToolbar(FredToolbar):
    """Housing Permits toolbar — adds view toggle (Raw / YoY %) to standard layout."""

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

        self.permits_label = self._info_label("Permits: --")
        layout.addWidget(self.permits_label)
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

    def update_info(self, total_permits=None, **kwargs):
        if total_permits is not None:
            self.permits_label.setText(f"Permits: {total_permits:.0f}K")
        self._update_timestamp()
