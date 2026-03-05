"""FRED Toolbar Base — Shared toolbar infrastructure for all FRED modules."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.modules.module_toolbar import ModuleToolbar


class FredToolbar(ModuleToolbar):
    """
    Base toolbar for all FRED modules.

    Adds: Lookback combo | [info section] between Home and Settings.

    Subclasses MUST implement:
        setup_info_section(layout) — add module-specific info labels after lookback
        update_info(**kwargs) — update those labels with data

    Subclasses MAY override:
        get_lookback_options() — default: ["1Y", "2Y", "5Y", "10Y", "20Y", "Max"]
        get_default_lookback_index() — default: 2 (5Y)
        supports_custom_date() — default: False; if True, adds "Custom" option
    """

    lookback_changed = Signal(str)

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._previous_lookback_index = self.get_default_lookback_index()
        super().__init__(theme_manager, parent)

    # ── Configuration hooks (override in subclass) ────────────────────────

    def get_lookback_options(self) -> list:
        """Return list of lookback option strings."""
        return ["1Y", "2Y", "5Y", "10Y", "20Y", "Max"]

    def get_default_lookback_index(self) -> int:
        """Return default index into lookback options."""
        return 2  # 5Y

    def supports_custom_date(self) -> bool:
        """If True, add a 'Custom' option that opens a date picker."""
        return False

    def setup_info_section(self, layout: QHBoxLayout):
        """Add module-specific info labels to the toolbar layout.

        Called between the lookback combo and the stretch.
        Use self._sep() to add separators.
        """
        pass

    def update_info(self, **kwargs):
        """Update module-specific info labels with data."""
        pass

    # ── Center content (called by ModuleToolbar._setup_ui) ────────────────

    def setup_center(self, layout: QHBoxLayout):
        layout.addWidget(self._sep())

        layout.addWidget(self._control_label("Lookback:"))

        if self.supports_custom_date():
            self.lookback_combo = self._combo(min_width=110, max_width=160)
            for opt in self.get_lookback_options():
                self.lookback_combo.addItem(opt, opt)
            self.lookback_combo.addItem("Custom", "Custom")
        else:
            self.lookback_combo = self._combo(items=self.get_lookback_options())

        self.lookback_combo.setCurrentIndex(self.get_default_lookback_index())
        self.lookback_combo.currentIndexChanged.connect(self._on_lookback_changed)
        layout.addWidget(self.lookback_combo)

        layout.addWidget(self._sep())

        # Module-specific info section
        self.setup_info_section(layout)

    # ── Lookback handling ─────────────────────────────────────────────────

    def _on_lookback_changed(self, index: int):
        if self.supports_custom_date():
            text = self.lookback_combo.itemText(index)
            data = self.lookback_combo.itemData(index)
            if data == "Custom" and text == "Custom":
                from app.ui.modules.cpi.widgets.custom_start_date_dialog import CustomStartDateDialog
                dialog = CustomStartDateDialog(self.theme_manager, parent=self.window())
                if dialog.exec():
                    date_str = dialog.get_start_date()
                    if date_str:
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
            self._previous_lookback_index = index

        self.lookback_changed.emit(self.lookback_combo.currentText())

    def set_active_lookback(self, lookback: str):
        for i in range(self.lookback_combo.count()):
            if self.lookback_combo.itemText(i) == lookback:
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(i)
                self._previous_lookback_index = i
                self.lookback_combo.blockSignals(False)
                return
