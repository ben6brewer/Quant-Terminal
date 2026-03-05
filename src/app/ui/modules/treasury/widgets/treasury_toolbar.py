"""Treasury Toolbar - Home button, view tabs, curve/lookback controls, info labels, settings."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QButtonGroup,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import ThemedDialog, DateInputWidget, NoScrollComboBox
from app.ui.modules.module_toolbar import ModuleToolbar


# Lookback options: (label, trading_days)  — -1 = custom
LOOKBACK_OPTIONS = [
    ("1Y", 252),
    ("2Y", 504),
    ("5Y", 1260),
    ("10Y", 2520),
    ("20Y", 5040),
    ("Max", None),
    ("Custom", -1),
]

# Overlay period presets for the curve view
OVERLAY_PERIODS = [
    ("1W", "1 Week Ago"),
    ("1M", "1 Month Ago"),
    ("6M", "6 Months Ago"),
    ("1Y", "1 Year Ago"),
    ("2Y", "2 Years Ago"),
    ("5Y", "5 Years Ago"),
]

# Interpolation methods
INTERPOLATION_OPTIONS = ["Cubic Spline", "Nelson-Siegel", "Linear"]


class CustomDateDialog(ThemedDialog):
    """Dialog for selecting a custom overlay date."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._selected_date: Optional[str] = None
        super().__init__(theme_manager, "Custom Date Overlay", parent, min_width=350)

    def _setup_content(self, layout: QVBoxLayout):
        desc = QLabel("Enter a date to overlay on the yield curve:")
        desc.setWordWrap(True)
        desc.setObjectName("description_label")
        layout.addWidget(desc)

        date_row = QHBoxLayout()
        date_row.setSpacing(10)

        date_label = QLabel("Date:")
        date_label.setObjectName("field_label")
        date_row.addWidget(date_label)

        self.date_input = DateInputWidget()
        self.date_input.setFixedWidth(150)
        self.date_input.setFixedHeight(36)
        date_row.addWidget(self.date_input)

        date_row.addStretch()
        layout.addLayout(date_row)

        info = QLabel("Format: YYYY-MM-DD. Date must be in the past.")
        info.setObjectName("noteLabel")
        layout.addWidget(info)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(100, 36)
        ok_btn.setObjectName("defaultButton")
        ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def _on_ok(self):
        date_text = self.date_input.text().strip()
        if date_text and len(date_text) == 10:
            self._selected_date = date_text
            self.accept()

    def get_date(self) -> Optional[str]:
        return self._selected_date


class TreasuryToolbar(ModuleToolbar):
    """Toolbar with home button, view tabs, curve/lookback controls, info bar, and settings."""

    view_changed = Signal(int)           # 0=Curve, 1=Rates, 2=Spread
    lookback_changed = Signal(str)       # "1Y", "2Y", ... or ISO date string
    interpolation_changed = Signal(str)  # "Cubic Spline", "Nelson-Siegel", "Linear"
    overlay_toggled = Signal(str, bool)  # period key, active state
    custom_date_selected = Signal(str)   # YYYY-MM-DD
    overlay_cleared = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._previous_lookback_index = 1  # Default: 2Y
        self._custom_start_date = None
        self._overlay_buttons: dict[str, QPushButton] = {}
        self._active_overlays: set[str] = set()
        super().__init__(theme_manager, parent)

    def setup_center(self, layout: QHBoxLayout):
        # View tab buttons
        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)

        view_names = ["Curve", "Rates", "Spread"]
        self._view_buttons = []
        for i, name in enumerate(view_names):
            btn = QPushButton(name)
            btn.setObjectName("viewTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumWidth(90)
            btn.setFixedHeight(40)
            if i == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, idx=i: self._on_view_tab_clicked(idx))
            layout.addWidget(btn)
            self.view_group.addButton(btn)
            self._view_buttons.append(btn)

        # ============ Curve zone (visible when Curve tab active) ============
        self._curve_zone = QWidget()
        self._curve_zone.setObjectName("curve_zone")
        curve_layout = QHBoxLayout(self._curve_zone)
        curve_layout.setContentsMargins(0, 0, 0, 0)
        curve_layout.setSpacing(8)

        curve_layout.addWidget(self._sep())

        # Interpolation dropdown
        interp_label = QLabel("Fit:")
        interp_label.setObjectName("control_label")
        curve_layout.addWidget(interp_label)

        self.interp_combo = NoScrollComboBox()
        self.interp_combo.setMinimumWidth(120)
        self.interp_combo.setMaximumWidth(160)
        self.interp_combo.setFixedHeight(40)
        self.interp_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.interp_combo.addItems(INTERPOLATION_OPTIONS)
        self.interp_combo.currentTextChanged.connect(self.interpolation_changed.emit)
        curve_layout.addWidget(self.interp_combo)

        curve_layout.addWidget(self._sep())

        # Overlay period buttons
        for key, tooltip in OVERLAY_PERIODS:
            btn = QPushButton(key)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(40)
            btn.setMinimumWidth(40)
            btn.setMaximumWidth(55)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn.setCheckable(True)
            btn.setObjectName("overlay_btn")
            btn.clicked.connect(lambda checked, k=key: self._on_overlay_toggled(k, checked))
            curve_layout.addWidget(btn)
            self._overlay_buttons[key] = btn

        # Custom date button
        self.custom_btn = QPushButton("Custom")
        self.custom_btn.setFixedHeight(40)
        self.custom_btn.setMinimumWidth(60)
        self.custom_btn.setMaximumWidth(80)
        self.custom_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.custom_btn.clicked.connect(self._on_custom_clicked)
        curve_layout.addWidget(self.custom_btn)

        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedHeight(40)
        self.clear_btn.setMinimumWidth(50)
        self.clear_btn.setMaximumWidth(70)
        self.clear_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        curve_layout.addWidget(self.clear_btn)

        layout.addWidget(self._curve_zone)

        # ============ Lookback zone (visible when Rates/Spread active) ============
        self._lookback_zone = QWidget()
        self._lookback_zone.setObjectName("lookback_zone")
        lb_layout = QHBoxLayout(self._lookback_zone)
        lb_layout.setContentsMargins(0, 0, 0, 0)
        lb_layout.setSpacing(8)

        lb_layout.addWidget(self._sep())

        lookback_label = QLabel("Lookback:")
        lookback_label.setObjectName("control_label")
        lb_layout.addWidget(lookback_label)

        self.lookback_combo = NoScrollComboBox()
        self.lookback_combo.setMinimumWidth(110)
        self.lookback_combo.setMaximumWidth(160)
        self.lookback_combo.setFixedHeight(40)
        self.lookback_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, days in LOOKBACK_OPTIONS:
            self.lookback_combo.addItem(label, days)
        self.lookback_combo.setCurrentIndex(1)  # Default: 2Y
        self.lookback_combo.currentIndexChanged.connect(self._on_lookback_changed)
        lb_layout.addWidget(self.lookback_combo)

        layout.addWidget(self._lookback_zone)

        # Start with lookback zone hidden (Curve tab is default)
        self._lookback_zone.setVisible(False)

        # ============ Separator + Info labels ============
        layout.addWidget(self._sep())

        self.yield_label = QLabel("10Y: --")
        self.yield_label.setObjectName("info_label")
        layout.addWidget(self.yield_label)

        layout.addWidget(self._sep())

        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

    def get_extra_stylesheet(self) -> str:
        return """
            QWidget#curve_zone, QWidget#lookback_zone {
                background: transparent;
            }
        """

    def _on_view_tab_clicked(self, index: int):
        """Handle view tab click — update control visibility then emit signal."""
        self._update_control_visibility(index)
        self.view_changed.emit(index)

    def _update_control_visibility(self, view_index: int):
        """Show curve zone for Curve tab, lookback zone for Rates/Spread."""
        self._curve_zone.setVisible(view_index == 0)
        self._lookback_zone.setVisible(view_index != 0)

    # ---- Overlay controls ---------------------------------------------------

    def _on_overlay_toggled(self, key: str, checked: bool):
        if checked:
            self._active_overlays.add(key)
        else:
            self._active_overlays.discard(key)
        self.overlay_toggled.emit(key, checked)

    def _on_custom_clicked(self):
        dialog = CustomDateDialog(self.theme_manager, self)
        if dialog.exec():
            date_str = dialog.get_date()
            if date_str:
                self.custom_date_selected.emit(date_str)

    def _on_clear_clicked(self):
        self._active_overlays.clear()
        for btn in self._overlay_buttons.values():
            btn.setChecked(False)
        self.overlay_cleared.emit()

    # ---- Lookback controls --------------------------------------------------

    def _on_lookback_changed(self, index: int):
        data = self.lookback_combo.currentData()

        if data == -1:
            from app.ui.modules.cpi.widgets.custom_start_date_dialog import CustomStartDateDialog

            dialog = CustomStartDateDialog(self.theme_manager, parent=self.window())
            if dialog.exec():
                date_str = dialog.get_start_date()
                if date_str:
                    self._custom_start_date = date_str
                    self.lookback_combo.blockSignals(True)
                    self.lookback_combo.setItemText(index, date_str)
                    self.lookback_combo.blockSignals(False)
                    self._previous_lookback_index = index
                    self.lookback_changed.emit(date_str)
            else:
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(self._previous_lookback_index)
                self.lookback_combo.blockSignals(False)
            return

        self._custom_start_date = None
        self._previous_lookback_index = index
        label = self.lookback_combo.currentText()
        self.lookback_changed.emit(label)

    # ---- Public setters -----------------------------------------------------

    def set_active_view(self, index: int):
        """Set active view programmatically."""
        if 0 <= index < len(self._view_buttons):
            self._view_buttons[index].setChecked(True)
            self._update_control_visibility(index)

    def set_active_lookback(self, lookback: str):
        for i in range(self.lookback_combo.count()):
            if self.lookback_combo.itemText(i) == lookback:
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(i)
                self._previous_lookback_index = i
                self.lookback_combo.blockSignals(False)
                return

    def update_info(self, yield_10y=None, date_str=None):
        if yield_10y is not None:
            self.yield_label.setText(f"10Y: {yield_10y:.2f}%")
        self._update_timestamp()
