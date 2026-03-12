"""Productivity Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class ProductivityToolbar(FredToolbar):
    """Productivity toolbar — shows latest Productivity YoY% and ULC YoY%."""

    def get_lookback_options(self) -> list:
        return ["5Y", "10Y", "20Y", "Max"]

    def get_default_lookback_index(self) -> int:
        return 1  # 10Y

    def setup_info_section(self, layout):
        self.prod_label = self._info_label("Productivity: --")
        layout.addWidget(self.prod_label)
        layout.addWidget(self._sep())
        self.ulc_label = self._info_label("ULC: --")
        layout.addWidget(self.ulc_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, productivity=None, ulc=None, **kwargs):
        if productivity is not None:
            self.prod_label.setText(f"Productivity: {productivity:+.1f}%")
        if ulc is not None:
            self.ulc_label.setText(f"ULC: {ulc:+.1f}%")
        self._update_timestamp()
