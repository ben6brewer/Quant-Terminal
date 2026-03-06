"""JOLTS Toolbar - Home, lookback, view toggle, openings info, settings."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class JoltsToolbar(FredToolbar):
    """JOLTS toolbar — view toggle (Raw / YoY %) + latest openings reading."""

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

        self.openings_label = self._info_label("Openings: --")
        layout.addWidget(self.openings_label)
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

    def update_info(self, openings=None, **kwargs):
        if openings is not None:
            val_str = f"{openings/1000:.2f}M" if openings >= 1000 else f"{openings:,.0f}K"
            self.openings_label.setText(f"Openings: {val_str}")
        self._update_timestamp()
