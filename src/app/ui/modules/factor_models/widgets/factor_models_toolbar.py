"""Factor Models Toolbar — input, model, frequency, lookback, and run controls."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import NoScrollComboBox, PortfolioTickerComboBox
from app.ui.modules.module_toolbar import ModuleToolbar

from ..services.model_definitions import MODELS, MODEL_ORDER, FactorModelSpec
from ..services.custom_model_store import CustomModelStore


# Frequency options: label -> key
FREQUENCY_OPTIONS = [
    ("Daily", "daily"),
    ("Weekly", "weekly"),
    ("Monthly", "monthly"),
]

# Lookback options: label -> calendar days (None = max, -1 = custom)
LOOKBACK_OPTIONS = [
    ("1 Year", 365),
    ("2 Years", 730),
    ("5 Years", 1825),
    ("10 Years", 3650),
    ("Max", None),
    ("Custom", -1),
]

_CREATE_SENTINEL = "__create__"


class FactorModelsToolbar(ModuleToolbar):
    """Toolbar for the Factor Models module."""

    run_clicked = Signal()
    export_clicked = Signal()
    input_changed = Signal(str)  # raw combo value
    model_changed = Signal(str)  # model key
    frequency_changed = Signal(str)
    lookback_changed = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._custom_date_range = None
        self._previous_lookback_index = 2  # Default: 5 Years
        self._previous_model_index = 4  # Default: FF5+Mom
        self._custom_specs: dict[str, FactorModelSpec] = {}  # key -> spec
        super().__init__(theme_manager, parent)

        # Insert Export button at the end of the toolbar
        layout = self.layout()
        self.export_btn = QPushButton("Export")
        self.export_btn.setMinimumWidth(70)
        self.export_btn.setMaximumWidth(100)
        self.export_btn.setFixedHeight(40)
        self.export_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.export_btn.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self.export_btn)

    def has_settings_button(self) -> bool:
        return True

    def setup_center(self, layout: QHBoxLayout):
        layout.addStretch(1)

        # ── Input (ticker / portfolio) ───────────────────────────────────
        input_label = QLabel("Input:")
        input_label.setObjectName("control_label")
        layout.addWidget(input_label)
        self.input_combo = PortfolioTickerComboBox()
        self.input_combo.setMinimumWidth(120)
        self.input_combo.setMaximumWidth(220)
        self.input_combo.setFixedHeight(40)
        self.input_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.input_combo.value_changed.connect(self.input_changed.emit)
        layout.addWidget(self.input_combo)

        layout.addSpacing(8)

        # ── Model dropdown ───────────────────────────────────────────────
        model_label = QLabel("Model:")
        model_label.setObjectName("control_label")
        layout.addWidget(model_label)
        self.model_combo = NoScrollComboBox()
        self.model_combo.setMinimumWidth(140)
        self.model_combo.setMaximumWidth(200)
        self.model_combo.setFixedHeight(40)
        self.model_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.model_combo)

        # Edit button (visible only when a custom model is selected)
        self._edit_btn = QPushButton("\u270E")  # ✎ pencil
        self._edit_btn.setFixedSize(30, 40)
        self._edit_btn.setObjectName("edit_model_btn")
        self._edit_btn.setCursor(Qt.PointingHandCursor)
        self._edit_btn.setToolTip("Edit custom model")
        self._edit_btn.clicked.connect(self._on_edit_model)
        self._edit_btn.hide()
        layout.addWidget(self._edit_btn)

        # Populate model combo after edit button exists
        self._rebuild_model_combo()
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)

        layout.addSpacing(8)

        # ── Frequency dropdown ───────────────────────────────────────────
        freq_label = QLabel("Freq:")
        freq_label.setObjectName("control_label")
        layout.addWidget(freq_label)
        self.frequency_combo = NoScrollComboBox()
        self.frequency_combo.setMinimumWidth(85)
        self.frequency_combo.setMaximumWidth(120)
        self.frequency_combo.setFixedHeight(40)
        self.frequency_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, key in FREQUENCY_OPTIONS:
            self.frequency_combo.addItem(label, key)
        self.frequency_combo.setCurrentIndex(2)  # Default: Monthly
        self.frequency_combo.currentIndexChanged.connect(
            lambda _: self.frequency_changed.emit(self.get_frequency())
        )
        layout.addWidget(self.frequency_combo)

        layout.addSpacing(8)

        # ── Lookback dropdown ────────────────────────────────────────────
        lookback_label = QLabel("Lookback:")
        lookback_label.setObjectName("control_label")
        layout.addWidget(lookback_label)
        self.lookback_combo = NoScrollComboBox()
        self.lookback_combo.setMinimumWidth(85)
        self.lookback_combo.setMaximumWidth(120)
        self.lookback_combo.setFixedHeight(40)
        self.lookback_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, days in LOOKBACK_OPTIONS:
            self.lookback_combo.addItem(label, days)
        self.lookback_combo.setCurrentIndex(2)  # Default: 5Y
        self.lookback_combo.currentIndexChanged.connect(self._on_lookback_changed)
        layout.addWidget(self.lookback_combo)

        layout.addSpacing(8)

        # ── Run button ───────────────────────────────────────────────────
        self.run_btn = QPushButton("Run")
        self.run_btn.setMinimumWidth(80)
        self.run_btn.setMaximumWidth(140)
        self.run_btn.setFixedHeight(40)
        self.run_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.run_btn.setObjectName("run_btn")
        self.run_btn.clicked.connect(self.run_clicked.emit)
        layout.addWidget(self.run_btn)

    # ── Model combo helpers ──────────────────────────────────────────────

    def _rebuild_model_combo(self, select_key: str | None = None):
        """Rebuild the model dropdown with built-in + custom + create entry."""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        # Built-in models
        for key in MODEL_ORDER:
            spec = MODELS[key]
            self.model_combo.addItem(spec.name, key)

        # Custom models
        custom_models = CustomModelStore.list_models()
        self._custom_specs.clear()
        if custom_models:
            self.model_combo.insertSeparator(self.model_combo.count())
            for spec in custom_models:
                self._custom_specs[spec.key] = spec
                self.model_combo.addItem(spec.name, spec.key)

        # Create entry
        self.model_combo.insertSeparator(self.model_combo.count())
        self.model_combo.addItem("+ Create Custom...", _CREATE_SENTINEL)

        # Select requested key or default
        target = select_key or "ff5mom"
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == target:
                self.model_combo.setCurrentIndex(i)
                self._previous_model_index = i
                break

        self.model_combo.blockSignals(False)
        self._update_edit_button_visibility()

    def _update_edit_button_visibility(self):
        """Show edit button only when a custom model is selected."""
        key = self.model_combo.currentData()
        self._edit_btn.setVisible(key in self._custom_specs)

    def _on_model_changed(self, _index: int):
        """Handle model dropdown change — may trigger create dialog."""
        key = self.model_combo.currentData()

        if key == _CREATE_SENTINEL:
            self._open_create_dialog()
            return

        # Update state
        self._previous_model_index = self.model_combo.currentIndex()
        self._update_edit_button_visibility()

        # Update frequency availability
        spec = MODELS.get(key) or self._custom_specs.get(key)
        if spec:
            self._update_frequency_availability(spec)

        self.model_changed.emit(key)

    def _open_create_dialog(self):
        """Open the custom model creation dialog."""
        from .custom_model_dialog import CustomModelDialog

        dialog = CustomModelDialog(self.theme_manager, parent=self.window())
        if dialog.exec():
            result = dialog.get_result()
            if result:
                name, factors = result
                spec = CustomModelStore.save_model(name, factors)
                self._rebuild_model_combo(select_key=spec.key)
                self.model_changed.emit(spec.key)
                return

        # Cancelled — revert to previous model
        self.model_combo.blockSignals(True)
        self.model_combo.setCurrentIndex(self._previous_model_index)
        self.model_combo.blockSignals(False)
        self._update_edit_button_visibility()

    def _on_edit_model(self):
        """Open the custom model edit dialog for the currently selected custom model."""
        from .custom_model_dialog import CustomModelDialog

        key = self.model_combo.currentData()
        spec = self._custom_specs.get(key)
        if not spec:
            return

        dialog = CustomModelDialog(
            self.theme_manager, parent=self.window(), edit_spec=spec
        )
        if dialog.exec():
            if dialog.was_deleted:
                CustomModelStore.delete_model(key)
                self._rebuild_model_combo(select_key="ff5mom")
                self.model_changed.emit("ff5mom")
            else:
                result = dialog.get_result()
                if result:
                    name, factors = result
                    updated = CustomModelStore.update_model(key, name, factors)
                    self._rebuild_model_combo(select_key=updated.key)
                    self.model_changed.emit(updated.key)

    # ── Lookback handler ─────────────────────────────────────────────────

    def _on_lookback_changed(self, index: int):
        """Handle lookback change — may open custom date dialog."""
        data = self.lookback_combo.currentData()

        if data == -1:
            from app.ui.modules.analysis.widgets.custom_date_dialog import (
                CustomDateDialog,
            )

            dialog = CustomDateDialog(self.theme_manager, parent=self.window())
            if dialog.exec():
                self._custom_date_range = dialog.get_date_range()
                self._previous_lookback_index = index
                self.lookback_changed.emit()
            else:
                # Cancelled — revert
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(self._previous_lookback_index)
                self.lookback_combo.blockSignals(False)
            return

        self._custom_date_range = None
        self._previous_lookback_index = index
        self.lookback_changed.emit()

    # ── Frequency availability ───────────────────────────────────────────

    def _update_frequency_availability(self, spec: FactorModelSpec):
        """Disable frequency options below the model's min_frequency."""
        min_freq = spec.min_frequency
        freq_order = ["daily", "weekly", "monthly"]
        min_idx = freq_order.index(min_freq) if min_freq in freq_order else 0

        current_freq_key = self.frequency_combo.currentData()

        for i in range(self.frequency_combo.count()):
            item_key = self.frequency_combo.itemData(i)
            item_idx = freq_order.index(item_key) if item_key in freq_order else 0
            enabled = item_idx >= min_idx
            model = self.frequency_combo.model()
            item = model.item(i)
            if item:
                if enabled:
                    item.setFlags(item.flags() | Qt.ItemIsEnabled)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)

        current_idx = (
            freq_order.index(current_freq_key) if current_freq_key in freq_order else 0
        )
        if current_idx < min_idx:
            self.frequency_combo.setCurrentIndex(min_idx)

    # ── Public Getters ───────────────────────────────────────────────────

    def get_input_value(self) -> str:
        """Raw value from input combo (may include [Port] prefix)."""
        return self.input_combo.get_value()

    def get_model_key(self) -> str:
        return self.model_combo.currentData()

    def get_model_spec(self) -> FactorModelSpec | None:
        key = self.get_model_key()
        return MODELS.get(key) or self._custom_specs.get(key)

    def get_frequency(self) -> str:
        return self.frequency_combo.currentData()

    def get_lookback_days(self):
        return self.lookback_combo.currentData()

    @property
    def custom_date_range(self):
        """Return (start_iso, end_iso) tuple or None."""
        return self._custom_date_range

    # ── Public Setters (for restoring from settings) ─────────────────────

    def set_input_value(self, value: str):
        """Set the input combo value (ticker text or '[Port] name')."""
        self.input_combo.set_value(value)

    def set_portfolios(self, portfolios: list[str], current: str | None = None):
        """Populate input combo portfolio list."""
        self.input_combo.set_portfolios(portfolios, current)

    def set_model(self, key: str):
        self.model_combo.blockSignals(True)
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == key:
                self.model_combo.setCurrentIndex(i)
                self._previous_model_index = i
                break
        self.model_combo.blockSignals(False)
        self._update_edit_button_visibility()

    def set_frequency(self, freq: str):
        self.frequency_combo.blockSignals(True)
        for i in range(self.frequency_combo.count()):
            if self.frequency_combo.itemData(i) == freq:
                self.frequency_combo.setCurrentIndex(i)
                break
        self.frequency_combo.blockSignals(False)

    def set_lookback(self, days):
        self.lookback_combo.blockSignals(True)
        for i in range(self.lookback_combo.count()):
            data = self.lookback_combo.itemData(i)
            if data == days or (days is None and data is None):
                self.lookback_combo.setCurrentIndex(i)
                self._previous_lookback_index = i
                break
        self.lookback_combo.blockSignals(False)

