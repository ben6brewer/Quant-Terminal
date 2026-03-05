"""Corporate Spreads Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class CorporateSpreadsToolbar(FredToolbar):
    """Corporate Spreads toolbar — shows latest Baa spread and HY OAS."""

    def setup_info_section(self, layout):
        self.baa_label = self._info_label("Baa: --")
        layout.addWidget(self.baa_label)
        layout.addWidget(self._sep())
        self.hy_label = self._info_label("HY OAS: --")
        layout.addWidget(self.hy_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, baa_spread=None, hy_oas=None, **kwargs):
        if baa_spread is not None:
            self.baa_label.setText(f"Baa: {baa_spread:.2f}%")
        if hy_oas is not None:
            self.hy_label.setText(f"HY OAS: {hy_oas:.0f}bp")
        self._update_timestamp()
