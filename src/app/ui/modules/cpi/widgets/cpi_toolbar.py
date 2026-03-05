"""CPI Toolbar - Home button, lookback dropdown, info labels, settings."""

from PySide6.QtWidgets import QLabel

from app.ui.modules.fred_toolbar import FredToolbar


class CpiToolbar(FredToolbar):
    """CPI toolbar — headline info, supports custom date lookback."""

    def get_default_lookback_index(self):
        return 1  # 2Y

    def supports_custom_date(self):
        return True

    def setup_info_section(self, layout):
        self.headline_label = QLabel("Headline: --")
        self.headline_label.setObjectName("info_label")
        layout.addWidget(self.headline_label)
        layout.addWidget(self._sep())
        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, headline=None, date_str=None, **kwargs):
        if headline is not None:
            self.headline_label.setText(f"Headline: {headline:.1f}%")
        self._update_timestamp()
