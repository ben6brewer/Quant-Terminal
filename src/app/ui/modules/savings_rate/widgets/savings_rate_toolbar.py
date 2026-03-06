"""Savings Rate Toolbar — Home, lookback, savings rate stat."""

from app.ui.modules.fred_toolbar import FredToolbar


class SavingsRateToolbar(FredToolbar):
    """Savings Rate toolbar — stat display only, no view toggle."""

    def setup_info_section(self, layout):
        self.rate_label = self._info_label("Savings Rate: --")
        layout.addWidget(self.rate_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, savings_rate=None, **kwargs):
        if savings_rate is not None:
            self.rate_label.setText(f"Savings Rate: {savings_rate:.1f}%")
        self._update_timestamp()
