"""Fed Funds Rate Toolbar — Home, lookback, EFFR stat, settings."""

from app.ui.modules.fred_toolbar import FredToolbar


class FedFundsRateToolbar(FredToolbar):
    """Fed Funds Rate toolbar — shows latest EFFR reading."""

    def get_default_lookback_index(self):
        return 5  # Max

    def setup_info_section(self, layout):
        self.effr_label = self._info_label("EFFR: --")
        layout.addWidget(self.effr_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, effr=None, **kwargs):
        if effr is not None:
            self.effr_label.setText(f"EFFR: {effr:.2f}%")
        self._update_timestamp()
