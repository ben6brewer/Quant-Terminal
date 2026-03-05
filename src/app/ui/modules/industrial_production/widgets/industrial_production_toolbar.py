"""Industrial Production Toolbar — Home, lookback, IP Index / Capacity Util stats."""

from app.ui.modules.fred_toolbar import FredToolbar


class IndustrialProductionToolbar(FredToolbar):
    """Industrial Production toolbar — shows IP Index and Capacity Utilization."""

    def setup_info_section(self, layout):
        self.ip_label = self._info_label("IP Index: --")
        layout.addWidget(self.ip_label)
        layout.addWidget(self._sep())
        self.cap_label = self._info_label("Cap. Util: --")
        layout.addWidget(self.cap_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, ip_index=None, capacity_util=None, **kwargs):
        if ip_index is not None:
            self.ip_label.setText(f"IP Index: {ip_index:.1f}")
        if capacity_util is not None:
            self.cap_label.setText(f"Cap. Util: {capacity_util:.1f}%")
        self._update_timestamp()
