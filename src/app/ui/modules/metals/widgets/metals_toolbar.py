"""Metals Toolbar — Home, lookback, view toggle, latest prices."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Normalized", "Raw"]


class MetalsToolbar(FredToolbar):
    """Metals toolbar — view toggle (Normalized / Raw) + latest prices."""

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

        self.gold_label = self._info_label("Au: --")
        layout.addWidget(self.gold_label)
        layout.addWidget(self._sep())
        self.silver_label = self._info_label("Ag: --")
        layout.addWidget(self.silver_label)
        layout.addWidget(self._sep())
        self.copper_label = self._info_label("Cu: --")
        layout.addWidget(self.copper_label)
        layout.addWidget(self._sep())
        self.platinum_label = self._info_label("Pt: --")
        layout.addWidget(self.platinum_label)
        layout.addWidget(self._sep())
        self.palladium_label = self._info_label("Pd: --")
        layout.addWidget(self.palladium_label)
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

    def update_info(self, gold=None, silver=None, copper=None,
                    platinum=None, palladium=None, **kwargs):
        if gold is not None:
            self.gold_label.setText(f"Au: ${gold:,.0f}")
        if silver is not None:
            self.silver_label.setText(f"Ag: ${silver:.2f}")
        if copper is not None:
            self.copper_label.setText(f"Cu: ${copper:.2f}")
        if platinum is not None:
            self.platinum_label.setText(f"Pt: ${platinum:,.0f}")
        if palladium is not None:
            self.palladium_label.setText(f"Pd: ${palladium:,.0f}")
        self._update_timestamp()
