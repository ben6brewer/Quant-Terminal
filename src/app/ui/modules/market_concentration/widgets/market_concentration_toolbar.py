"""Market Concentration Toolbar — FredToolbar with metric dropdown + N spinbox."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy

from app.ui.modules.fred_toolbar import FredToolbar
from app.ui.modules.monte_carlo.widgets.monte_carlo_controls import NoScrollSpinBox


METRICS = ["Top N %", "HHI"]
N_DEPENDENT_METRICS = {"Top N %"}


class MarketConcentrationToolbar(FredToolbar):
    """Toolbar with metric selector and top-N spinbox."""

    metric_changed = Signal(str)
    top_n_changed = Signal(int)

    def setup_center(self, layout: QHBoxLayout):
        # Standard lookback combo (+ optional view/data combos from kwargs)
        super().setup_center(layout)

        # Metric dropdown
        layout.addWidget(self._sep())
        layout.addWidget(self._control_label("Metric:"))
        self.metric_combo = self._combo(items=METRICS, min_width=120, max_width=160)
        self.metric_combo.currentIndexChanged.connect(self._on_metric_changed_internal)
        layout.addWidget(self.metric_combo)

        # N spinbox — initial range is generous; the actual cap is tightened
        # to the constituent count once the first fetch lands (see set_max_n).
        layout.addWidget(self._sep())
        layout.addWidget(self._control_label("N:"))
        self.n_spinbox = NoScrollSpinBox()
        self.n_spinbox.setRange(1, 1000)
        self.n_spinbox.setValue(10)
        self.n_spinbox.setFixedHeight(40)
        self.n_spinbox.setFixedWidth(85)
        self.n_spinbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.n_spinbox.valueChanged.connect(self.top_n_changed.emit)
        layout.addWidget(self.n_spinbox)

    def _on_metric_changed_internal(self, _index: int):
        metric = self.metric_combo.currentText()
        # N is irrelevant for HHI → grey it out
        self.n_spinbox.setEnabled(metric in N_DEPENDENT_METRICS)
        self.metric_changed.emit(metric)

    def set_active_metric(self, metric: str):
        if not hasattr(self, "metric_combo"):
            return
        for i in range(self.metric_combo.count()):
            if self.metric_combo.itemText(i) == metric:
                self.metric_combo.blockSignals(True)
                self.metric_combo.setCurrentIndex(i)
                self.metric_combo.blockSignals(False)
                self.n_spinbox.setEnabled(metric in N_DEPENDENT_METRICS)
                return

    def set_top_n(self, n: int):
        if not hasattr(self, "n_spinbox"):
            return
        try:
            n_int = int(n)
        except (TypeError, ValueError):
            return
        upper = self.n_spinbox.maximum()
        self.n_spinbox.blockSignals(True)
        self.n_spinbox.setValue(max(1, min(upper, n_int)))
        self.n_spinbox.blockSignals(False)

    def set_max_n(self, max_n: int):
        """Tighten the spinbox upper bound (called after data lands so the
        spinbox cap matches the actual constituent count)."""
        if not hasattr(self, "n_spinbox"):
            return
        try:
            cap = max(1, int(max_n))
        except (TypeError, ValueError):
            return
        self.n_spinbox.blockSignals(True)
        self.n_spinbox.setMaximum(cap)
        # If the current value exceeds the new cap, clamp it.
        if self.n_spinbox.value() > cap:
            self.n_spinbox.setValue(cap)
        self.n_spinbox.blockSignals(False)
