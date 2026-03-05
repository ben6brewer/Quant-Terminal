"""Demographics Toolbar - Home, lookback, as-of info, settings."""

from app.ui.modules.fred_toolbar import FredToolbar


class DemographicsToolbar(FredToolbar):
    """Demographics toolbar — shows as-of date."""

    def setup_info_section(self, layout):
        self.info_label = self._info_label("")
        layout.addWidget(self.info_label)

    def update_info(self, date_str=None, **kwargs):
        if date_str is not None:
            self.info_label.setText(f"As of {date_str}")
