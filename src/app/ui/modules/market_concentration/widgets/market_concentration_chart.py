"""Market Concentration Chart — single-line chart with metric-aware Y-axis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.date_index_axis import DraggableIndexDateAxisItem
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem

if TYPE_CHECKING:
    import pandas as pd


LINE_COLOR = "#FFA500"  # orange — distinct from default chart palette


class MarketConcentrationChart(BaseChart):
    """Single-line chart of a market concentration metric over time."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._values: Optional[np.ndarray] = None
        self._date_labels: list = []
        self._line_item = None
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_hover_tooltip = True
        self._metric: str = "Top N %"
        self._n: int = 10

        self._setup_plots()
        self._setup_crosshair()
        self._setup_tooltip()
        self._setup_placeholder()

    def _setup_plots(self):
        self._bottom_axis = DraggableIndexDateAxisItem(orientation="bottom")
        self._right_axis = DraggableAxisItem(orientation="right")
        self._right_axis.setWidth(60)
        self.plot_item = self.addPlot(
            axisItems={"bottom": self._bottom_axis, "right": self._right_axis}
        )
        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMouseEnabled(x=True, y=True)
        self.plot_item.showAxis("left", False)
        self.plot_item.showAxis("right", True)
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

    def _setup_crosshair(self):
        self._crosshair_v, self._crosshair_h = self._create_crosshair(
            self.plot_item, self.view_box
        )
        self.setMouseTracking(True)

    def _setup_tooltip(self):
        self._tooltip = self._create_tooltip_label()
        self._apply_tooltip_style()

    def _apply_tooltip_style(self):
        bg = self._get_background_rgb()
        text = self._get_label_text_color()
        accent = self._get_theme_accent_color()
        self._tooltip.setStyleSheet(
            f"background-color: rgba({bg[0]}, {bg[1]}, {bg[2]}, 230);"
            f"color: rgb({text[0]}, {text[1]}, {text[2]});"
            f"border: 1px solid rgb({accent[0]}, {accent[1]}, {accent[2]});"
            f"border-radius: 4px; padding: 8px 10px; font-size: 12px;"
            f'font-family: "Menlo", "Consolas", "Courier New";'
        )

    def _setup_placeholder(self):
        self._placeholder = QLabel("Loading market concentration data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        if self.plot_item:
            self.plot_item.clear()
            self._line_item = None
            self._values = None
            self._dates = None
            self._setup_crosshair()

    def update_data(self, series_df, metric: str, n: int, settings: dict):
        """Render the metric series.

        series_df: pd.DataFrame with one 'value' column, datetime index
        metric:    name of the metric (controls Y-axis formatting)
        n:         current N value (for the title/tooltip when relevant)
        """
        import pandas as pd

        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._metric = metric
        self._n = n

        if series_df is None or series_df.empty:
            self.show_placeholder("No concentration data available.")
            return

        series = series_df["value"].dropna() if "value" in series_df.columns else series_df.iloc[:, 0].dropna()
        if series.empty:
            self.show_placeholder("No concentration data available.")
            return

        self._placeholder.setVisible(False)

        self._dates = series.index.values
        self._values = series.values.astype(float)
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]

        self.plot_item.clear()
        self._setup_crosshair()

        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))

        self._line_item = self.plot_item.plot(
            x, self._values, pen=pg.mkPen(color=LINE_COLOR, width=2)
        )
        self._line_item.setClipToView(True)

        # Y-axis range per metric
        valid = self._values[~np.isnan(self._values)]
        if len(valid) == 0:
            self.show_placeholder("No concentration data available.")
            return

        if metric == "Top N %":
            # Pad the data range slightly; cap at 0–100
            y_min = max(0.0, float(valid.min()) - 5.0)
            y_max = min(100.0, float(valid.max()) + 5.0)
            if y_max - y_min < 10:
                y_max = min(100.0, y_min + 10.0)
            self.plot_item.setYRange(y_min, y_max, padding=0)
        else:
            # HHI: auto-range with floor at 0
            y_min = max(0.0, float(valid.min()))
            y_max = float(valid.max())
            pad = (y_max - y_min) * 0.1 if y_max != y_min else 10.0
            self.plot_item.setYRange(max(0.0, y_min - pad), y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )

    # ── Mouse interaction ─────────────────────────────────────────────────

    def _on_mouse_move(self, ev):
        if self._dates is None or len(self._dates) == 0:
            return
        mouse_pos = ev.pos()
        scene_pos = self.mapToScene(mouse_pos)
        vb_rect = self.view_box.sceneBoundingRect()
        if not vb_rect.contains(scene_pos):
            self._hide_interactive()
            return
        view_pos = self.view_box.mapSceneToView(scene_pos)
        n = len(self._dates)
        idx = int(max(0, min(round(view_pos.x()), n - 1)))
        if self._show_crosshair:
            self._crosshair_v.setPos(view_pos.x())
            self._crosshair_h.setPos(view_pos.y())
            self._crosshair_v.setVisible(True)
            self._crosshair_h.setVisible(True)
        self._update_tooltip(idx, mouse_pos)

    def _on_mouse_leave(self, ev):
        self._hide_interactive()

    def _hide_interactive(self):
        if self._crosshair_v:
            self._crosshair_v.setVisible(False)
        if self._crosshair_h:
            self._crosshair_h.setVisible(False)
        if self._tooltip:
            self._tooltip.setVisible(False)

    def _format_value(self, v: float) -> str:
        if self._metric == "Top N %":
            return f"{v:.2f}%"
        if self._metric == "HHI":
            return f"{v:,.0f}"
        return f"{v:.2f}"

    def _metric_label(self) -> str:
        if self._metric == "Top N %":
            return f"Top {self._n} share"
        return self._metric

    def _update_tooltip(self, idx: int, mouse_pos):
        if not self._show_hover_tooltip:
            self._tooltip.setVisible(False)
            return
        if (
            self._dates is None
            or self._values is None
            or idx < 0
            or idx >= len(self._dates)
        ):
            self._tooltip.setVisible(False)
            return

        date_str = self._date_labels[idx] if idx < len(self._date_labels) else "?"
        v = self._values[idx]
        if np.isnan(v):
            self._tooltip.setVisible(False)
            return

        lines = [
            f"<b>{date_str}</b>",
            f'<span style="color:{LINE_COLOR};">\u25a0</span> '
            f"{self._metric_label()}: {self._format_value(v)}",
        ]
        self._tooltip.setText("<br>".join(lines))
        self._tooltip.adjustSize()
        tip_w, tip_h = self._tooltip.width(), self._tooltip.height()
        x = int(mouse_pos.x()) + 16
        y = int(mouse_pos.y()) - tip_h // 2
        if x + tip_w > self.width() - 8:
            x = int(mouse_pos.x()) - tip_w - 16
        if y < 8:
            y = 8
        if y + tip_h > self.height() - 8:
            y = self.height() - tip_h - 8
        self._tooltip.move(x, y)
        self._tooltip.setVisible(True)
        self._tooltip.raise_()

    def set_theme(self, theme: str):
        super().set_theme(theme)
        self._apply_tooltip_style()
        if self._line_item is not None:
            self._line_item.setPen(pg.mkPen(color=LINE_COLOR, width=2))
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        text_color = self._get_label_text_color()
        for axis_name in ("bottom", "right"):
            axis = self.plot_item.getAxis(axis_name)
            if axis:
                axis.setTextPen(text_color)
                axis.label.setDefaultTextColor(pg.mkColor(text_color))

    def showEvent(self, event):
        super().showEvent(event)
        if self._placeholder and self._placeholder.isVisible():
            self._placeholder.setGeometry(self.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._placeholder and self._placeholder.isVisible():
            self._placeholder.setGeometry(self.rect())
