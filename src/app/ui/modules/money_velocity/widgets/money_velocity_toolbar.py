"""Money Velocity Toolbar — Home, lookback, M2V stat, settings."""

from app.ui.modules.fred_toolbar import FredToolbar


class MoneyVelocityToolbar(FredToolbar):
    """Money Velocity toolbar — shows latest M2V reading."""

    def get_lookback_options(self):
        return ["5Y", "10Y", "20Y", "Max"]

    def get_default_lookback_index(self):
        return 3  # Max

    def setup_info_section(self, layout):
        self.m2v_label = self._info_label("M2V: --")
        layout.addWidget(self.m2v_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, m2v=None, **kwargs):
        if m2v is not None:
            self.m2v_label.setText(f"M2V: {m2v:.2f}")
        self._update_timestamp()
