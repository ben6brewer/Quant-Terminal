"""GDP Toolbar — Home, lookback, view toggle (Raw / YoY %), stats."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class GdpToolbar(FredToolbar):
    """GDP toolbar — adds view toggle (Raw / YoY %) to standard layout."""

    view_changed = Signal(str)

    def get_lookback_options(self):
        return ["5Y", "10Y", "20Y", "Max"]

    def get_default_lookback_index(self):
        return 1  # 10Y

    def setup_info_section(self, layout):
        layout.addWidget(self._control_label("View:"))

        self.view_combo = self._combo(items=VIEW_OPTIONS)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)

        layout.addWidget(self._sep())

        self.gdp_label = self._info_label("Real GDP: --")
        layout.addWidget(self.gdp_label)
        layout.addWidget(self._sep())
        self.growth_label = self._info_label("Growth: --")
        layout.addWidget(self.growth_label)
        layout.addWidget(self._sep())
        self.quarter_label = self._info_label("--")
        layout.addWidget(self.quarter_label)
        layout.addWidget(self._sep())

        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

    def set_active_view(self, view: str):
        for i in range(self.view_combo.count()):
            if self.view_combo.itemText(i) == view:
                self.view_combo.blockSignals(True)
                self.view_combo.setCurrentIndex(i)
                self.view_combo.blockSignals(False)
                return

    def update_info(self, real_gdp=None, gdp_growth=None, quarter=None, **kwargs):
        if real_gdp is not None:
            self.gdp_label.setText(f"Real GDP: ${real_gdp:.2f}T")
        if gdp_growth is not None:
            color = "#4CAF50" if gdp_growth >= 0 else "#EF5350"
            self.growth_label.setText(f"Growth: {gdp_growth:+.1f}%")
            self.growth_label.setStyleSheet(
                self.growth_label.styleSheet() + f"color: {color};"
            )
        if quarter is not None:
            self.quarter_label.setText(quarter)
        self._update_timestamp()
