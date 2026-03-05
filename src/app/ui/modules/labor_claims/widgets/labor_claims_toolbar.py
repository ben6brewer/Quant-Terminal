"""Labor Claims Toolbar - Home, lookback, claims info, settings."""

from app.ui.modules.fred_toolbar import FredToolbar


class LaborClaimsToolbar(FredToolbar):
    """Labor Claims toolbar — shows latest claims reading, supports custom date."""

    def supports_custom_date(self):
        return True

    def setup_info_section(self, layout):
        self.claims_label = self._info_label("Claims: --")
        layout.addWidget(self.claims_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, claims=None, **kwargs):
        if claims is not None:
            self.claims_label.setText(f"Claims: {claims:,.0f}")
        self._update_timestamp()
