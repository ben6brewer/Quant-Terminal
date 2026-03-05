"""Fed Balance Sheet Toolbar — Home, lookback, total assets stat, settings."""

from PySide6.QtWidgets import QLabel

from app.ui.modules.fred_toolbar import FredToolbar


class FedBalanceSheetToolbar(FredToolbar):
    """Fed Balance Sheet toolbar — shows latest Total Assets reading."""

    def get_default_lookback_index(self):
        return 3  # 10Y

    def setup_info_section(self, layout):
        self.assets_label = QLabel("Total Assets: --")
        self.assets_label.setObjectName("info_label")
        layout.addWidget(self.assets_label)
        layout.addWidget(self._sep())
        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, total_assets=None, **kwargs):
        if total_assets is not None:
            self.assets_label.setText(f"Total Assets: ${total_assets:.2f}T")
        self._update_timestamp()
