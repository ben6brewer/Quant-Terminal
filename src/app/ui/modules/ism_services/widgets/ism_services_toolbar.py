"""ISM Services Toolbar — Home, lookback, Services Activity stat."""

from app.ui.modules.fred_toolbar import FredToolbar


class IsmServicesToolbar(FredToolbar):
    """ISM Services toolbar — shows latest Services Activity value."""

    def get_default_lookback_index(self) -> int:
        return 3  # 10Y

    def setup_info_section(self, layout):
        self.services_label = self._info_label("Services: --")
        layout.addWidget(self.services_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, services=None, **kwargs):
        if services is not None:
            self.services_label.setText(f"Services: {services:.1f}")
        self._update_timestamp()
