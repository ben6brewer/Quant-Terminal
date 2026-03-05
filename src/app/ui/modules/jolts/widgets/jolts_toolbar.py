"""JOLTS Toolbar - Home, lookback, openings info, settings."""

from app.ui.modules.fred_toolbar import FredToolbar


class JoltsToolbar(FredToolbar):
    """JOLTS toolbar — shows latest openings reading, supports custom date."""

    def supports_custom_date(self):
        return True

    def setup_info_section(self, layout):
        self.openings_label = self._info_label("Openings: --")
        layout.addWidget(self.openings_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, openings=None, **kwargs):
        if openings is not None:
            val_str = f"{openings/1000:.2f}M" if openings >= 1000 else f"{openings:,.0f}K"
            self.openings_label.setText(f"Openings: {val_str}")
        self._update_timestamp()
