"""PCE Toolbar - Home, lookback, info, settings."""

from PySide6.QtWidgets import QLabel

from app.ui.modules.fred_toolbar import FredToolbar


class PceToolbar(FredToolbar):
    """PCE toolbar — shows latest PCE reading."""

    def setup_info_section(self, layout):
        self.pce_label = QLabel("PCE: --")
        self.pce_label.setObjectName("info_label")
        layout.addWidget(self.pce_label)
        layout.addWidget(self._sep())
        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, pce=None, **kwargs):
        if pce is not None:
            self.pce_label.setText(f"PCE: {pce:.2f}%")
        self._update_timestamp()
