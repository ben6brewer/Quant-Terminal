"""Energy Prices Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class EnergyPricesToolbar(FredToolbar):
    """Energy Prices toolbar — shows latest WTI, Brent, NatGas."""

    def setup_info_section(self, layout):
        self.wti_label = self._info_label("WTI: --")
        layout.addWidget(self.wti_label)
        layout.addWidget(self._sep())
        self.brent_label = self._info_label("Brent: --")
        layout.addWidget(self.brent_label)
        layout.addWidget(self._sep())
        self.natgas_label = self._info_label("NatGas: --")
        layout.addWidget(self.natgas_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, wti=None, brent=None, natgas=None, **kwargs):
        if wti is not None:
            self.wti_label.setText(f"WTI: ${wti:.2f}")
        if brent is not None:
            self.brent_label.setText(f"Brent: ${brent:.2f}")
        if natgas is not None:
            self.natgas_label.setText(f"NatGas: ${natgas:.2f}")
        self._update_timestamp()
