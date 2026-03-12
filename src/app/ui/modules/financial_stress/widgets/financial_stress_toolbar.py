"""Financial Stress Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class FinancialStressToolbar(FredToolbar):
    """Financial Stress toolbar — shows latest STLFSI and KCFSI values."""

    def get_default_lookback_index(self) -> int:
        return 3  # 10Y

    def setup_info_section(self, layout):
        self.stlfsi_label = self._info_label("STLFSI: --")
        layout.addWidget(self.stlfsi_label)
        layout.addWidget(self._sep())
        self.kcfsi_label = self._info_label("KCFSI: --")
        layout.addWidget(self.kcfsi_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, stlfsi=None, kcfsi=None, **kwargs):
        if stlfsi is not None:
            self.stlfsi_label.setText(f"STLFSI: {stlfsi:+.2f}")
        if kcfsi is not None:
            self.kcfsi_label.setText(f"KCFSI: {kcfsi:+.2f}")
        self._update_timestamp()
