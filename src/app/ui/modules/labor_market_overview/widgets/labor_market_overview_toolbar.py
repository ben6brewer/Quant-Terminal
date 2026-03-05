"""Labor Market Overview Toolbar - Home button, lookback, info labels, settings."""

from app.ui.modules.fred_toolbar import FredToolbar


class LaborMarketOverviewToolbar(FredToolbar):
    """Labor Market Overview toolbar — shows latest UNRATE reading."""

    def setup_info_section(self, layout):
        self.unrate_label = self._info_label("UNRATE: --")
        layout.addWidget(self.unrate_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, unrate=None, **kwargs):
        if unrate is not None:
            self.unrate_label.setText(f"UNRATE: {unrate:.1f}%")
        self._update_timestamp()
