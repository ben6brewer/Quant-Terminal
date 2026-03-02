"""Treasury Rates Chart - Multi-line time series of selected maturities over time."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.date_index_axis import DraggableIndexDateAxisItem
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem
from app.ui.widgets.charting.overlays.crosshair_overlay import CrosshairOverlay

if TYPE_CHECKING:
    import pandas as pd

# Color palette for rate lines (one per maturity)
RATE_COLORS: Dict[str, tuple] = {
    "1M": (150, 150, 150),
    "3M": (180, 180, 180),
    "6M": (200, 180, 120),
    "1Y": (200, 150, 80),
    "2Y": (0, 200, 255),
    "3Y": (0, 180, 200),
    "5Y": (100, 255, 100),
    "7Y": (80, 200, 80),
    "10Y": (255, 180, 0),
    "20Y": (255, 100, 100),
    "30Y": (255, 80, 180),
    "Fed Funds": (255, 80, 80),
}


class TreasuryRatesChart(BaseChart):
    """Multi-line time series chart of selected Treasury maturities."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        # Data
        self._dates: Optional[np.ndarray] = None
        self._series_data: Dict[str, np.ndarray] = {}  # label -> values
        self._date_labels: list = []
        self._n_points: int = 0

        # Settings
        self._show_gridlines = True
        self._show_crosshair = True

        # Plot items
        self._line_items: list = []
        self._legend = None

        self._setup_plots()
        self._setup_crosshair()
        self._setup_overlay()
        self._setup_tooltip()
        self._setup_placeholder()

    def _setup_plots(self):
        """Create plot item with right-side Y-axis."""
        self._bottom_axis = DraggableIndexDateAxisItem(orientation="bottom")
        self._right_axis = DraggableAxisItem(orientation="right")
        self._right_axis.setWidth(70)

        self.plot_item = self.addPlot(
            axisItems={
                "bottom": self._bottom_axis,
                "right": self._right_axis,
            }
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

    def _setup_overlay(self):
        self._overlay = CrosshairOverlay(
            chart=self,
            plot_item=self.plot_item,
            view_box=self.view_box,
            value_formatter=lambda v: f"{v:.3f}%",
        )

    def _setup_tooltip(self):
        """Create floating tooltip for multi-line values."""
        self._tooltip = QLabel(self)
        self._tooltip.setVisible(False)
        self._tooltip.setWordWrap(False)
        self._tooltip.setTextFormat(Qt.RichText)
        self._apply_tooltip_style()

    def _apply_tooltip_style(self):
        bg = self._get_background_rgb()
        text = self._get_label_text_color()
        accent = self._get_theme_accent_color()
        self._tooltip.setStyleSheet(
            f"background-color: rgba({bg[0]}, {bg[1]}, {bg[2]}, 230);"
            f"color: rgb({text[0]}, {text[1]}, {text[2]});"
            f"border: 1px solid rgb({accent[0]}, {accent[1]}, {accent[2]});"
            f"border-radius: 4px;"
            f"padding: 8px 10px;"
            f"font-size: 12px;"
            f"font-family: monospace;"
        )

    def _setup_placeholder(self):
        self._placeholder = QLabel("Loading rates data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading rates data..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        self._clear_data()
        if self.plot_item:
            self.plot_item.clear()
            self._setup_crosshair()

    def _clear_data(self):
        self._dates = None
        self._series_data = {}
        self._date_labels = []
        self._n_points = 0
        self._line_items = []
        if self._legend is not None:
            try:
                self._legend.clear()
                self._legend.scene().removeItem(self._legend)
            except Exception:
                pass
            self.plot_item.legend = None
            self._legend = None
        self._overlay.set_data([], 0)

    def update_data(self, df: "pd.DataFrame", settings: dict):
        """Plot multi-line time series for selected maturities.

        Args:
            df: DataFrame with DatetimeIndex and tenor columns, sliced to lookback.
            settings: Display settings dict.
        """
        import pandas as pd

        if df is None or df.empty:
            self.show_placeholder("No rates data available.")
            return

        self._placeholder.setVisible(False)

        # Apply settings
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        show_value = settings.get("show_value_label", True)
        show_date = settings.get("show_date_label", True)
        rate_series = settings.get("rate_series", ["2Y", "5Y", "10Y", "30Y"])
        show_ff = settings.get("show_fed_funds_rate", False)

        # Determine which columns to plot
        columns_to_plot = [s for s in rate_series if s in df.columns]
        if show_ff and "Fed Funds" in df.columns:
            columns_to_plot.append("Fed Funds")

        if not columns_to_plot:
            self.show_placeholder("No rate series available.")
            return

        # Drop rows where ALL selected columns are NaN
        plot_df = df[columns_to_plot].dropna(how="all")
        if plot_df.empty:
            self.show_placeholder("No rates data available.")
            return

        # Store data for crosshair
        self._dates = plot_df.index.values
        self._n_points = len(plot_df)
        self._date_labels = [
            pd.Timestamp(d).strftime("%Y-%m-%d") for d in self._dates
        ]

        # Store per-series arrays
        self._series_data = {}
        for col in columns_to_plot:
            self._series_data[col] = plot_df[col].values.astype(float)

        # Update overlay
        self._overlay.set_data(self._date_labels, self._n_points)
        self._overlay.set_visible(show_value, show_date)

        # Clear and redraw
        self.plot_item.clear()
        self._line_items = []
        if self._legend is not None:
            try:
                self._legend.clear()
                self._legend.scene().removeItem(self._legend)
            except Exception:
                pass
            self.plot_item.legend = None
            self._legend = None
        self._setup_crosshair()

        # Date index for bottom axis
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)

        # Add legend
        self._legend = self.plot_item.addLegend(offset=(60, 5))
        self._legend.setBrush(pg.mkBrush(color=(0, 0, 0, 100)))

        # Plot each series
        x = np.arange(self._n_points)
        for col in columns_to_plot:
            values = self._series_data[col]
            color = RATE_COLORS.get(col, (200, 200, 200))
            width = 2.0 if col != "Fed Funds" else 1.5
            style = Qt.SolidLine if col != "Fed Funds" else Qt.DashLine

            pen = pg.mkPen(color=color, width=width, style=style)
            line = self.plot_item.plot(x, values, pen=pen, name=col)
            line.setClipToView(True)
            self._line_items.append(line)

        # Y range
        all_vals = np.concatenate([v for v in self._series_data.values()])
        valid = all_vals[~np.isnan(all_vals)]
        if len(valid) > 0:
            y_min, y_max = float(np.nanmin(valid)), float(np.nanmax(valid))
            y_range = y_max - y_min if y_max != y_min else abs(y_max) or 1.0
            padding = y_range * 0.08
            self.plot_item.setYRange(y_min - padding, y_max + padding, padding=0)

        # X range
        self.plot_item.setXRange(0, self._n_points - 1, padding=0.02)

        # Gridlines
        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )

    # -- Mouse Events ---------------------------------------------------------

    def _on_mouse_move(self, ev):
        if self._n_points == 0:
            return

        mouse_pos = ev.pos()
        scene_pos = self.mapToScene(mouse_pos)
        vb_rect = self.view_box.sceneBoundingRect()

        if not vb_rect.contains(scene_pos):
            self._hide_interactive()
            return

        view_pos = self.view_box.mapSceneToView(scene_pos)
        idx = int(max(0, min(round(view_pos.x()), self._n_points - 1)))

        # Update crosshair
        if self._show_crosshair:
            self._crosshair_v.setPos(view_pos.x())
            self._crosshair_h.setPos(view_pos.y())
            self._crosshair_v.setVisible(True)
            self._crosshair_h.setVisible(True)

        # Update overlay
        self._overlay.update(mouse_pos)

        # Update tooltip
        self._update_tooltip(idx, mouse_pos)

    def _update_tooltip(self, idx: int, mouse_pos):
        if idx < 0 or idx >= len(self._date_labels):
            self._tooltip.setVisible(False)
            return

        date_str = self._date_labels[idx]
        lines = [f"<b>{date_str}</b>"]

        for label, values in self._series_data.items():
            val = values[idx]
            color = RATE_COLORS.get(label, (200, 200, 200))
            if not np.isnan(val):
                lines.append(
                    f'<span style="color:rgb({color[0]},{color[1]},{color[2]});">'
                    f'\u25a0</span> {label}: <b>{val:.3f}%</b>'
                )

        self._tooltip.setText("<br>".join(lines))
        self._tooltip.adjustSize()

        tip_w = self._tooltip.width()
        tip_h = self._tooltip.height()
        x = int(mouse_pos.x()) + 16
        y = int(mouse_pos.y()) - tip_h // 2

        widget_w = self.width()
        widget_h = self.height()
        if x + tip_w > widget_w - 8:
            x = int(mouse_pos.x()) - tip_w - 16
        if y < 8:
            y = 8
        if y + tip_h > widget_h - 8:
            y = widget_h - tip_h - 8

        self._tooltip.move(x, y)
        self._tooltip.setVisible(True)
        self._tooltip.raise_()

    def _on_mouse_leave(self, ev):
        self._hide_interactive()

    def _hide_interactive(self):
        if self._crosshair_v:
            self._crosshair_v.setVisible(False)
        if self._crosshair_h:
            self._crosshair_h.setVisible(False)
        self._overlay.hide()
        self._tooltip.setVisible(False)

    # -- Theme ----------------------------------------------------------------

    def _apply_gridlines(self):
        if self.plot_item is None:
            return
        grid_color = self._get_contrasting_grid_color()
        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )
        self.plot_item.getAxis('bottom').setPen(color=grid_color, width=1)
        if self.plot_item.getAxis('right'):
            self.plot_item.getAxis('right').setPen(color=grid_color, width=1)

    def set_theme(self, theme: str):
        super().set_theme(theme)
        self._overlay.update_theme()
        self._apply_tooltip_style()

        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )

        text_color = self._get_label_text_color()
        for axis_name in ("bottom", "right"):
            axis = self.plot_item.getAxis(axis_name)
            if axis:
                axis.setTextPen(text_color)
                axis.label.setDefaultTextColor(pg.mkColor(text_color))

        # Update legend text color
        if self._legend is not None:
            self._legend.setLabelTextColor(text_color)

    def showEvent(self, event):
        super().showEvent(event)
        if self._placeholder and self._placeholder.isVisible():
            self._placeholder.setGeometry(self.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._placeholder and self._placeholder.isVisible():
            self._placeholder.setGeometry(self.rect())
