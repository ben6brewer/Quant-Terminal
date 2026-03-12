"""ISM Manufacturing Toolbar — Home, lookback, PMI stat."""

from app.ui.modules.fred_toolbar import FredToolbar


class IsmManufacturingToolbar(FredToolbar):
    """ISM Manufacturing toolbar — shows latest PMI value."""

    def get_default_lookback_index(self) -> int:
        return 3  # 10Y

    def setup_info_section(self, layout):
        self.pmi_label = self._info_label("PMI: --")
        layout.addWidget(self.pmi_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, pmi=None, **kwargs):
        if pmi is not None:
            self.pmi_label.setText(f"PMI: {pmi:.1f}")
        self._update_timestamp()
