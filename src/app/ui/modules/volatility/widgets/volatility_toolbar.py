"""Volatility Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class VolatilityToolbar(FredToolbar):
    """Volatility toolbar — shows latest VIX value."""

    def get_default_lookback_index(self) -> int:
        return 2  # 5Y

    def setup_info_section(self, layout):
        self.vix_label = self._info_label("VIX: --")
        layout.addWidget(self.vix_label)
        layout.addWidget(self._sep())
        self.move_label = self._info_label("MOVE: --")
        layout.addWidget(self.move_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, vix=None, move=None, **kwargs):
        if vix is not None:
            self.vix_label.setText(f"VIX: {vix:.1f}")
        if move is not None:
            self.move_label.setText(f"MOVE: {move:.1f}")
        self._update_timestamp()
