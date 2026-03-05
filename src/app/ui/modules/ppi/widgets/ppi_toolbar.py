"""PPI Toolbar - Home, lookback, info, settings."""

from PySide6.QtWidgets import QLabel

from app.ui.modules.fred_toolbar import FredToolbar


class PpiToolbar(FredToolbar):
    """PPI toolbar — shows latest PPI Final Demand reading."""

    def setup_info_section(self, layout):
        self.ppi_label = QLabel("PPI: --")
        self.ppi_label.setObjectName("info_label")
        layout.addWidget(self.ppi_label)
        layout.addWidget(self._sep())
        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, ppi_final=None, **kwargs):
        if ppi_final is not None:
            self.ppi_label.setText(f"PPI: {ppi_final:.2f}%")
        self._update_timestamp()
