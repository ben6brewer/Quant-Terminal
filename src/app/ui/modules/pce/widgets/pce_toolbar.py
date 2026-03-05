"""PCE Toolbar - Home, lookback, info, settings."""

from app.ui.modules.fred_toolbar import FredToolbar


class PceToolbar(FredToolbar):
    """PCE toolbar — shows latest PCE reading."""

    def setup_info_section(self, layout):
        self.pce_label = self._info_label("PCE: --")
        layout.addWidget(self.pce_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, pce=None, **kwargs):
        if pce is not None:
            self.pce_label.setText(f"PCE: {pce:.2f}%")
        self._update_timestamp()
