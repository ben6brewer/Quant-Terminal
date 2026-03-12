"""Sahm Rule Toolbar — Home, lookback, latest Sahm stat."""

from app.ui.modules.fred_toolbar import FredToolbar


class SahmRuleToolbar(FredToolbar):
    """Sahm Rule toolbar — shows latest Sahm Rule value."""

    def setup_info_section(self, layout):
        self.sahm_label = self._info_label("Sahm: --")
        layout.addWidget(self.sahm_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, sahm=None, **kwargs):
        if sahm is not None:
            self.sahm_label.setText(f"Sahm: {sahm:.2f}")
        self._update_timestamp()

    def get_default_lookback_index(self) -> int:
        return 5  # Max
