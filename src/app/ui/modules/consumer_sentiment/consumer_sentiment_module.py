"""Consumer Sentiment Module — University of Michigan Consumer Sentiment with recession shading."""

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.consumer.services import ConsumerFredService
from .widgets.consumer_sentiment_toolbar import ConsumerSentimentToolbar
from .widgets.consumer_sentiment_chart import ConsumerSentimentChart


class ConsumerSentimentModule(FredDataModule):
    """Consumer Sentiment module — UMCSENT line with recession shading."""

    SETTINGS_FILENAME = "consumer_sentiment_settings.json"
    DEFAULT_SETTINGS = {
        "show_recession_bands": True,
        "show_gridlines": True,
        "show_crosshair": True,
        "show_hover_tooltip": True,
        "lookback": "5Y",
    }

    def create_toolbar(self):
        return ConsumerSentimentToolbar(self.theme_manager)

    def create_chart(self):
        return ConsumerSentimentChart()

    def get_fred_service(self):
        return ConsumerFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching consumer sentiment data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch consumer sentiment data."

    def update_toolbar_info(self, result):
        stats = ConsumerFredService.get_latest_stats(result)
        if stats:
            self.toolbar.update_info(
                sentiment=stats.get("sentiment"),
                sentiment_mom=stats.get("sentiment_mom"),
            )

    def extract_chart_data(self, result):
        sent_df = self.slice_data(result.get("sentiment"))
        usrec_df = result.get("usrec")
        return (sent_df, usrec_df)

    def get_settings_options(self):
        return [
            ("show_recession_bands", "Show recession shading"),
            ("show_gridlines", "Show gridlines"),
            ("show_crosshair", "Show crosshair"),
            ("show_hover_tooltip", "Show hover tooltip"),
        ]

    def get_settings_dialog_title(self):
        return "Consumer Sentiment Settings"
