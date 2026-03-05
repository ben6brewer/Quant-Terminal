"""Money Supply Toolbar — Home, lookback, view toggle, M2 stat, settings."""

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Signal

from app.ui.widgets.common import NoScrollComboBox
from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class MoneySupplyToolbar(FredToolbar):
    """Money Supply toolbar — adds view toggle (Raw / YoY %) to standard layout."""

    view_changed = Signal(str)

    def get_default_lookback_index(self):
        return 3  # 10Y

    def setup_info_section(self, layout):
        # View combo (inserted before info labels)
        view_label = QLabel("View:")
        view_label.setObjectName("control_label")
        layout.addWidget(view_label)

        self.view_combo = NoScrollComboBox()
        self.view_combo.setMinimumWidth(90)
        self.view_combo.setMaximumWidth(130)
        self.view_combo.setFixedHeight(40)
        self.view_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for opt in VIEW_OPTIONS:
            self.view_combo.addItem(opt)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)

        layout.addWidget(self._sep())

        self.m2_label = QLabel("M2: --")
        self.m2_label.setObjectName("info_label")
        layout.addWidget(self.m2_label)

        layout.addWidget(self._sep())

        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

    def set_active_view(self, view: str):
        for i in range(self.view_combo.count()):
            if self.view_combo.itemText(i) == view:
                self.view_combo.blockSignals(True)
                self.view_combo.setCurrentIndex(i)
                self.view_combo.blockSignals(False)
                return

    def update_info(self, m2=None, **kwargs):
        if m2 is not None:
            self.m2_label.setText(f"M2: ${m2:.2f}T")
        self._update_timestamp()
