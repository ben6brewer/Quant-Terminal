"""Mortgage Rates Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class MortgageRatesToolbar(FredToolbar):
    """Mortgage Rates toolbar — shows latest 30Y and 15Y rates."""

    def setup_info_section(self, layout):
        self.rate30_label = self._info_label("30Y: --")
        layout.addWidget(self.rate30_label)
        layout.addWidget(self._sep())
        self.rate15_label = self._info_label("15Y: --")
        layout.addWidget(self.rate15_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, rate_30y=None, rate_15y=None, **kwargs):
        if rate_30y is not None:
            self.rate30_label.setText(f"30Y: {rate_30y:.2f}%")
        if rate_15y is not None:
            self.rate15_label.setText(f"15Y: {rate_15y:.2f}%")
        self._update_timestamp()
