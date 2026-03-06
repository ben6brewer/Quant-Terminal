"""Delinquency Rates Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class DelinquencyRatesToolbar(FredToolbar):
    """Delinquency Rates toolbar — CC delinquency stat."""

    def get_lookback_options(self):
        return ["5Y", "10Y", "20Y", "Max"]

    def get_default_lookback_index(self) -> int:
        return 1  # 10Y

    def setup_info_section(self, layout):
        self.delinq_label = self._info_label("CC Delinq: --")
        layout.addWidget(self.delinq_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, cc_delinquency=None, **kwargs):
        if cc_delinquency is not None:
            self.delinq_label.setText(f"CC Delinq: {cc_delinquency:.1f}%")
        self._update_timestamp()
