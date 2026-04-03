"""Stock Heatmap Settings Dialog — checkboxes + color scale input."""

from PySide6.QtWidgets import (
    QCheckBox, QDialogButtonBox, QDoubleSpinBox, QHBoxLayout, QLabel,
)

from app.ui.widgets.common.themed_dialog import ThemedDialog


class HeatmapSettingsDialog(ThemedDialog):

    def __init__(self, theme_manager, current_settings, parent=None):
        self._current = current_settings
        self._checks = {}
        self._scale_spin = None
        super().__init__(theme_manager, "Stock Heatmap Settings", parent, min_width=340)

    def _setup_content(self, layout):
        # Checkbox toggles
        for key, label in [
            ("show_hover_tooltip", "Show hover tooltip"),
            ("show_ticker", "Show ticker label"),
            ("show_logo", "Show logo"),
            ("click_to_chart", "Click tile to open chart"),
        ]:
            cb = QCheckBox(label)
            cb.setChecked(self._current.get(key, True))
            self._checks[key] = cb
            layout.addWidget(cb)

        # Color scale input
        row = QHBoxLayout()
        row.addWidget(QLabel("Color scale (\u00b1%):"))
        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(0.5, 50.0)
        self._scale_spin.setSingleStep(0.5)
        self._scale_spin.setDecimals(1)
        self._scale_spin.setValue(self._current.get("color_scale", 3.0))
        self._scale_spin.setFixedWidth(80)
        row.addWidget(self._scale_spin)
        row.addStretch()
        layout.addLayout(row)

        # Buttons
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_settings(self):
        settings = {k: cb.isChecked() for k, cb in self._checks.items()}
        settings["color_scale"] = self._scale_spin.value()
        return settings
