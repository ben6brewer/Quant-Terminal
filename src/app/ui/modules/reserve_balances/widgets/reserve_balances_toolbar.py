"""Reserve Balances Toolbar — Home, lookback, reserves stat, settings."""

from app.ui.modules.fred_toolbar import FredToolbar


class ReserveBalancesToolbar(FredToolbar):
    """Reserve Balances toolbar — shows latest Reserve Balances reading."""

    def get_default_lookback_index(self):
        return 5  # Max

    def setup_info_section(self, layout):
        self.reserves_label = self._info_label("Reserves: --")
        layout.addWidget(self.reserves_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, reserves=None, **kwargs):
        if reserves is not None:
            self.reserves_label.setText(f"Reserves: ${reserves:.2f}T")
        self._update_timestamp()
