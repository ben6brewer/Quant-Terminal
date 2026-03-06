"""Consumer Sentiment Toolbar — Home, lookback, view toggle, UMCSENT stat, MoM change."""

from PySide6.QtCore import Signal

from app.ui.modules.fred_toolbar import FredToolbar

VIEW_OPTIONS = ["Raw", "YoY %"]


class ConsumerSentimentToolbar(FredToolbar):
    """Consumer Sentiment toolbar — view toggle (Raw / YoY %) + UMCSENT index and MoM change."""

    view_changed = Signal(str)

    def setup_info_section(self, layout):
        layout.addWidget(self._control_label("View:"))

        self.view_combo = self._combo(items=VIEW_OPTIONS)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.view_changed.emit(self.view_combo.currentText())
        )
        layout.addWidget(self.view_combo)

        layout.addWidget(self._sep())

        self.sentiment_label = self._info_label("UMCSENT: --")
        layout.addWidget(self.sentiment_label)
        layout.addWidget(self._sep())
        self.mom_label = self._info_label("MoM: --")
        layout.addWidget(self.mom_label)
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

    def update_info(self, sentiment=None, sentiment_mom=None, **kwargs):
        if sentiment is not None:
            self.sentiment_label.setText(f"UMCSENT: {sentiment:.1f}")
        if sentiment_mom is not None:
            color = "#4CAF50" if sentiment_mom >= 0 else "#EF5350"
            self.mom_label.setText(f"MoM: {sentiment_mom:+.1f}")
            self.mom_label.setStyleSheet(
                self.mom_label.styleSheet() + f"color: {color};"
            )
        self._update_timestamp()
