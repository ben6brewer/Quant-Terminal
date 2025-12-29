"""UI Widgets - Organized by domain (navigation, charting, common)."""

from __future__ import annotations

# Re-export for backward compatibility (deprecated - use specific imports)
from app.ui.modules.chart.widgets import (
    PriceChart,
    CreateIndicatorDialog,
    ChartSettingsDialog,
)
from app.ui.modules.chart.widgets.depth_chart import OrderBookPanel, DepthChartWidget
from app.ui.modules.chart.widgets.order_book_ladder import OrderBookLadderWidget

__all__ = [
    "PriceChart",
    "CreateIndicatorDialog",
    "ChartSettingsDialog",
    "OrderBookPanel",
    "DepthChartWidget",
    "OrderBookLadderWidget",
]