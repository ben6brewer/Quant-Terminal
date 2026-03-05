"""Vehicle Sales Toolbar — Home, lookback, stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class VehicleSalesToolbar(FredToolbar):
    """Vehicle Sales toolbar — shows latest total vehicle sales."""

    def setup_info_section(self, layout):
        self.total_label = self._info_label("Total: --")
        layout.addWidget(self.total_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, vehicle_total=None, **kwargs):
        if vehicle_total is not None:
            self.total_label.setText(f"Total: {vehicle_total:.1f}M SAAR")
        self._update_timestamp()
