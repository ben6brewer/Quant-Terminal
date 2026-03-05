"""Consumer Sentiment Toolbar — Home, lookback, UMCSENT stat, MoM change."""

from app.ui.modules.fred_toolbar import FredToolbar


class ConsumerSentimentToolbar(FredToolbar):
    """Consumer Sentiment toolbar — shows UMCSENT index and MoM change."""

    def setup_info_section(self, layout):
        self.sentiment_label = self._info_label("UMCSENT: --")
        layout.addWidget(self.sentiment_label)
        layout.addWidget(self._sep())
        self.mom_label = self._info_label("MoM: --")
        layout.addWidget(self.mom_label)
        layout.addWidget(self._sep())
        self.updated_label = self._info_label("", "info_label_muted")
        layout.addWidget(self.updated_label)

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
