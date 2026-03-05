"""Financial Conditions Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class FinancialConditionsToolbar(FredToolbar):
    """Financial Conditions toolbar — shows latest NFCI value + direction."""

    def setup_info_section(self, layout):
        self.nfci_label = self._info_label("NFCI: --")
        layout.addWidget(self.nfci_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, nfci=None, nfci_prev=None, **kwargs):
        if nfci is not None:
            arrow = ""
            if nfci_prev is not None:
                arrow = " \u2191" if nfci > nfci_prev else " \u2193" if nfci < nfci_prev else ""
            self.nfci_label.setText(f"NFCI: {nfci:+.2f}{arrow}")
        self._update_timestamp()
