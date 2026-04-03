"""Stock Heatmap Module — Multi-market treemap coloured by price change."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.yfinance_base_module import YFinanceDataModule
from app.ui.modules.fred_toolbar import FredToolbar
from .services.sp500_heatmap_service import SP500HeatmapService, MARKETS
from .widgets.stock_heatmap_widget import StockHeatmapWidget

HEATMAP_LOOKBACK = {
    "1D": 2,   # need 2 rows to compute 1-day change
    "1W": 5,
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "YTD": None,  # handled specially in slice_data
    "1Y": 252,
}


class _StockHeatmapToolbar(FredToolbar):
    """Toolbar with market selector and custom date support."""

    market_changed = Signal(str)

    def __init__(self, theme_manager, *, market_options=None, **kwargs):
        self._market_options = market_options or MARKETS
        super().__init__(theme_manager, **kwargs)

    def supports_custom_date(self):
        return True

    def setup_center(self, layout: QHBoxLayout):
        # Market selector first
        layout.addWidget(self._sep())
        layout.addWidget(self._control_label("Market:"))
        self.market_combo = self._combo(items=self._market_options)
        self.market_combo.currentIndexChanged.connect(
            lambda _: self.market_changed.emit(self.market_combo.currentText())
        )
        layout.addWidget(self.market_combo)

        # Then the standard lookback + view + data combos
        super().setup_center(layout)

    def set_active_market(self, market: str):
        for i in range(self.market_combo.count()):
            if self.market_combo.itemText(i) == market:
                self.market_combo.blockSignals(True)
                self.market_combo.setCurrentIndex(i)
                self.market_combo.blockSignals(False)
                return


class StockHeatmapModule(YFinanceDataModule):
    SETTINGS_FILENAME = "stock_heatmap_settings.json"
    DEFAULT_SETTINGS = {
        "market": "S&P 500",
        "view_mode": "Sector Grouped",
        "sizing_mode": "Market Cap",
        "lookback": "1W",
        "show_hover_tooltip": True,
        "show_ticker": True,
        "show_logo": True,
        "color_scale": 3.0,
        "click_to_chart": True,
    }
    VIEW_MODE = "view_mode"
    DATA_MODE = "sizing_mode"

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._progress_timer: Optional[QTimer] = None
        super().__init__(theme_manager, parent)
        self.chart.ticker_clicked.connect(self._on_ticker_clicked)
        self.toolbar.market_changed.connect(self._on_market_changed)
        # Restore saved market
        saved_market = self.settings_manager.get_setting("market")
        if saved_market and saved_market in MARKETS:
            self.toolbar.set_active_market(saved_market)

    def create_toolbar(self):
        return _StockHeatmapToolbar(
            self.theme_manager,
            market_options=MARKETS,
            lookback_options=["1D", "1W", "1M", "3M", "6M", "YTD", "1Y"],
            default_lookback_index=1,  # 1W
            view_options=["Sector Grouped", "Flat"],
            data_mode_options=["Market Cap", "Equal Weight"],
        )

    def create_chart(self):
        return StockHeatmapWidget()

    def get_data_service(self):
        market = self.settings_manager.get_setting("market") or "S&P 500"
        return lambda: SP500HeatmapService.fetch_all_data(market=market)

    def get_loading_message(self) -> str:
        market = self.settings_manager.get_setting("market") or "S&P 500"
        return f"Fetching {market} data"

    def get_lookback_map(self) -> dict:
        return HEATMAP_LOOKBACK

    def create_settings_dialog(self, current_settings):
        from .widgets.heatmap_settings_dialog import HeatmapSettingsDialog
        return HeatmapSettingsDialog(self.theme_manager, current_settings, parent=self)

    # ── Market change ─────────────────────────────────────────────────────

    def _on_market_changed(self, market: str):
        self.settings_manager.update_settings({"market": market})
        self._data = None  # force re-fetch for new market
        self._fetch_data()

    # ── Click to chart ────────────────────────────────────────────────────

    def _on_ticker_clicked(self, ticker: str):
        if not self.settings_manager.get_setting("click_to_chart"):
            return
        hub = self.window()
        if not hasattr(hub, "open_module"):
            return
        hub.open_module("charts")
        chart_module = hub.modules.get("charts")
        if chart_module is not None:
            chart_module.load_ticker_max(ticker)

    # ── Progress polling ──────────────────────────────────────────────────

    def _fetch_data(self):
        self._start_progress_polling()
        super()._fetch_data()

    def _start_progress_polling(self):
        if self._progress_timer is None:
            self._progress_timer = QTimer(self)
            self._progress_timer.timeout.connect(self._poll_progress)
        self._progress_timer.start(400)

    def _stop_progress_polling(self):
        if self._progress_timer is not None:
            self._progress_timer.stop()

    def _poll_progress(self):
        stage = SP500HeatmapService.progress_stage
        current = SP500HeatmapService.progress_current
        total = SP500HeatmapService.progress_total
        if self._loading_overlay and self._loading_overlay.isVisible():
            if total > 0 and current > 0:
                self._loading_overlay.set_progress(current, total, stage)
            elif stage:
                self._loading_overlay.set_message(stage)

    def _on_data_fetched(self, result):
        self._stop_progress_polling()
        super()._on_data_fetched(result)

    def _on_fetch_error(self, error_msg: str):
        self._stop_progress_polling()
        super()._on_fetch_error(error_msg)

    # ── Data slicing ──────────────────────────────────────────────────────

    def slice_data(self, df):
        if df is None or df.empty:
            return df
        lb = self._current_lookback
        # Custom ISO date string
        if isinstance(lb, str) and "-" in lb and lb not in HEATMAP_LOOKBACK:
            return df.loc[lb:]
        # YTD: slice from Jan 1 of current year
        if lb == "YTD":
            start = f"{datetime.now().year}-01-01"
            result = df.loc[start:]
            return result if not result.empty else df
        count = HEATMAP_LOOKBACK.get(lb)
        if count is None:
            return df
        return df.tail(count)

    def extract_chart_data(self, result: Dict) -> tuple:
        import pandas as pd

        sp500_info = result.get("sp500_info")
        price_data = result.get("price_data")
        logo_paths = result.get("logo_paths", {})

        if sp500_info is None or price_data is None:
            return (None,)

        # Slice price data to lookback window
        sliced = self.slice_data(price_data)
        if sliced is None or len(sliced) < 2:
            return (None,)

        # Compute percent change for each ticker
        first_row = sliced.iloc[0]
        last_row = sliced.iloc[-1]

        sizing_mode = self.settings_manager.get_setting("sizing_mode")
        heatmap_data: List[Dict] = []

        for _, row in sp500_info.iterrows():
            ticker = row["ticker"]
            if ticker not in sliced.columns:
                continue

            first_price = first_row.get(ticker)
            last_price = last_row.get(ticker)

            if pd.isna(first_price) or pd.isna(last_price) or first_price == 0:
                continue

            pct_change = (last_price / first_price - 1) * 100
            market_cap = row.get("market_cap", 0)
            weight = 1.0 if sizing_mode == "Equal Weight" else max(market_cap, 1.0)

            entry = {
                "ticker": ticker,
                "name": row.get("name", ticker),
                "sector": row.get("sector", "Other"),
                "sub_industry": row.get("sub_industry", ""),
                "market_cap": market_cap,
                "pct_change": float(pct_change),
                "weight": weight,
            }
            logo = logo_paths.get(ticker) or logo_paths.get(ticker.upper())
            if logo:
                entry["logo_path"] = logo
            heatmap_data.append(entry)

        return (heatmap_data,)
