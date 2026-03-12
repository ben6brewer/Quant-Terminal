"""Recession Indicators Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class RecessionIndicatorsToolbar(FredToolbar):
    """Recession Indicators toolbar — shows latest Recession Prob and Sahm Rule."""

    def setup_info_section(self, layout):
        self.prob_label = self._info_label("Prob: --")
        layout.addWidget(self.prob_label)
        layout.addWidget(self._sep())
        self.sahm_label = self._info_label("Sahm: --")
        layout.addWidget(self.sahm_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, recession_prob=None, sahm=None, **kwargs):
        if recession_prob is not None:
            self.prob_label.setText(f"Prob: {recession_prob:.2f}%")
        if sahm is not None:
            self.sahm_label.setText(f"Sahm: {sahm:.2f}")
        self._update_timestamp()

    def get_default_lookback_index(self) -> int:
        return 5  # Max
