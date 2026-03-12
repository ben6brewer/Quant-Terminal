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

    Can be used declaratively (no subclass needed) via keyword args:
        FredToolbar(theme_mgr,
            view_options=["Raw", "YoY %"],
            stat_labels=[("wti_label", "WTI: --")],
            lookback_options=["1Y", "5Y", "10Y", "Max"],
            default_lookback_index=1,
        )

    Or subclassed with:
        setup_info_section(layout)
        update_info(**kwargs)
        get_lookback_options()
        get_default_lookback_index()
        supports_custom_date()
    """

    lookback_changed = Signal(str)
    view_changed = Signal(str)
    data_mode_changed = Signal(str)

    def __init__(self, theme_manager: ThemeManager, parent=None, *,
                 view_options=None,
                 data_mode_options=None,
                 stat_labels=None,
                 lookback_options=None,
                 default_lookback_index=None):
        self._view_options = view_options
        self._data_mode_options = data_mode_options
        self._stat_labels = stat_labels
        self._lookback_options_override = lookback_options
        self._default_lookback_index_override = default_lookback_index
        self._previous_lookback_index = self.get_default_lookback_index()
        super().__init__(theme_manager, parent)

    # ── Configuration hooks (override in subclass) ────────────────────────

    def get_lookback_options(self) -> list:
        if self._lookback_options_override is not None:
            return self._lookback_options_override
        return ["1Y", "2Y", "5Y", "10Y", "20Y", "Max"]

    def get_default_lookback_index(self) -> int:
        if hasattr(self, "_default_lookback_index_override") and self._default_lookback_index_override is not None:
            return self._default_lookback_index_override
        return 2  # 5Y

    def supports_custom_date(self) -> bool:
        return False

    def setup_info_section(self, layout: QHBoxLayout):
        """Add module-specific info labels. Auto-generates from constructor args if set."""
        if not self._view_options and not self._data_mode_options and not self._stat_labels:
            return

        if self._view_options:
            layout.addWidget(self._control_label("View:"))
            self.view_combo = self._combo(items=self._view_options)
            self.view_combo.currentIndexChanged.connect(
                lambda _: self.view_changed.emit(self.view_combo.currentText())
            )
            layout.addWidget(self.view_combo)
            layout.addWidget(self._sep())

        if self._data_mode_options:
            layout.addWidget(self._control_label("Data:"))
            self.data_combo = self._combo(items=self._data_mode_options)
            self.data_combo.currentIndexChanged.connect(
                lambda _: self.data_mode_changed.emit(self.data_combo.currentText())
            )
            layout.addWidget(self.data_combo)
            layout.addWidget(self._sep())

        if self._stat_labels:
            for attr_name, default_text in self._stat_labels:
                label = self._info_label(default_text)
                setattr(self, attr_name, label)
                layout.addWidget(label)
                layout.addWidget(self._sep())

        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, **kwargs):
        pass

    # ── View/Data mode helpers ─────────────────────────────────────────────

    def set_active_view(self, view: str):
        if not hasattr(self, "view_combo"):
            return
        for i in range(self.view_combo.count()):
            if self.view_combo.itemText(i) == view:
                self.view_combo.blockSignals(True)
                self.view_combo.setCurrentIndex(i)
                self.view_combo.blockSignals(False)
                return

    def set_active_data_mode(self, mode: str):
        if not hasattr(self, "data_combo"):
            return
        for i in range(self.data_combo.count()):
            if self.data_combo.itemText(i) == mode:
                self.data_combo.blockSignals(True)
                self.data_combo.setCurrentIndex(i)
                self.data_combo.blockSignals(False)
                return

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
