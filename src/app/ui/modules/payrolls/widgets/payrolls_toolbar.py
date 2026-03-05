"""Payrolls Toolbar - Home, lookback, info label, settings."""

from PySide6.QtWidgets import QLabel

from app.ui.modules.fred_toolbar import FredToolbar


class PayrollsToolbar(FredToolbar):
    """Payrolls toolbar — shows latest payrolls MoM reading, supports custom date."""

    def supports_custom_date(self):
        return True

    def setup_info_section(self, layout):
        self.payrolls_label = QLabel("Payrolls: --")
        self.payrolls_label.setObjectName("info_label")
        layout.addWidget(self.payrolls_label)
        layout.addWidget(self._sep())
        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

    def update_info(self, payrolls_mom=None, **kwargs):
        if payrolls_mom is not None:
            sign = "+" if payrolls_mom >= 0 else ""
            self.payrolls_label.setText(f"Payrolls: {sign}{payrolls_mom:,.0f}K")
        self._update_timestamp()
