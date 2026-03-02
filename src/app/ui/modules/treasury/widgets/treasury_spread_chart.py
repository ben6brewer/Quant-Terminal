"""Treasury Spread Chart - 10Y-2Y spread with inversion shading."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.date_index_axis import DraggableIndexDateAxisItem
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem
from app.ui.widgets.charting.overlays.crosshair_overlay import CrosshairOverlay

if TYPE_CHECKING:
    import pandas as pd


class TreasurySpreadChart(BaseChart):
    """10Y-2Y Treasury spread chart with zero-line and inversion shading."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        # Data
        self._dates: Optional[np.ndarray] = None
        self._values: Optional[np.ndarray] = None
        self._date_labels: list = []

        # Settings
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_inversion_shading = True
        self._show_zero_line = True

        # Plot items
        self._line_item = None
        self._fill_items: list = []
        self._ref_lines: list = []

        self._setup_plots()
        self._setup_crosshair()
        self._setup_overlay()
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
            value_formatter=lambda v: f"{v:.2f}%",
        )

    def _setup_placeholder(self):
        self._placeholder = QLabel("Loading spread data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading spread data..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        self._clear_data()
        if self.plot_item:
            self.plot_item.clear()
            self._setup_crosshair()

    def _clear_data(self):
        self._dates = None
        self._values = None
        self._date_labels = []
        self._line_item = None
        self._fill_items = []
        self._ref_lines = []
        self._overlay.set_data([], 0)

    def update_data(self, df: "pd.DataFrame", settings: dict):
        """Plot 10Y-2Y spread line with inversion shading.

        Args:
            df: DataFrame with DatetimeIndex, sliced to lookback period.
                Must contain "10Y-2Y Spread" column, or "10Y" and "2Y" to compute.
            settings: Display settings dict.
        """
        import pandas as pd

        if df is None or df.empty:
            self.show_placeholder("No spread data available.")
            return

        # Get spread series
        if "10Y-2Y Spread" in df.columns:
            spread = df["10Y-2Y Spread"].dropna()
        elif "10Y" in df.columns and "2Y" in df.columns:
            spread = (df["10Y"] - df["2Y"]).dropna()
        else:
            self.show_placeholder("No spread data available (need 10Y and 2Y columns).")
            return

        if spread.empty:
            self.show_placeholder("No spread data available.")
            return

        self._placeholder.setVisible(False)

        # Apply settings
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_inversion_shading = settings.get("show_inversion_shading", True)
        self._show_zero_line = settings.get("show_zero_line", True)

        show_value = settings.get("show_value_label", True)
        show_date = settings.get("show_date_label", True)
        line_color = settings.get("line_color", None)
        line_width = settings.get("line_width", 2)
        line_style = settings.get("line_style", Qt.SolidLine)

        # Store data
        self._dates = spread.index.values
        self._values = spread.values.astype(float)
        self._date_labels = [
            pd.Timestamp(d).strftime("%Y-%m-%d") for d in self._dates
        ]

        # Update overlay
        self._overlay.set_data(self._date_labels, len(self._values))
        self._overlay.set_visible(show_value, show_date)

        # Clear and redraw
        self.plot_item.clear()
        self._line_item = None
        self._fill_items = []
        self._ref_lines = []
        self._setup_crosshair()

        # Date index for bottom axis
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)

        n = len(self._values)
        x = np.arange(n)

        # Zero reference line
        if self._show_zero_line:
            zero_pen = pg.mkPen(color=(150, 150, 150), width=1.0, style=Qt.DashLine)
            zero_line = pg.InfiniteLine(pos=0.0, angle=0, pen=zero_pen)
            self.plot_item.addItem(zero_line, ignoreBounds=True)
            self._ref_lines.append(zero_line)

        # Inversion shading (red fill below zero)
        if self._show_inversion_shading:
            self._add_inversion_shading(x, self._values)

        # Spread line
        color = line_color if line_color else self._get_theme_accent_color()
        pen = pg.mkPen(color=color, width=line_width, style=line_style)
        self._line_item = self.plot_item.plot(x, self._values, pen=pen)
        self._line_item.setClipToView(True)

        # Y-axis range
        y_min, y_max = float(np.nanmin(self._values)), float(np.nanmax(self._values))
        y_range = y_max - y_min if y_max != y_min else abs(y_max) or 1.0
        padding = y_range * 0.08
        self.plot_item.setYRange(y_min - padding, y_max + padding, padding=0)

        # X range
        self.plot_item.setXRange(0, n - 1, padding=0.02)

        # Gridlines
        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )

    def _add_inversion_shading(self, x: np.ndarray, values: np.ndarray):
        """Add red shading for negative (inverted) spread regions."""
        # Create clipped arrays: show only negative portions
        zero_line = np.zeros_like(values)
        negative_vals = np.minimum(values, 0.0)

        # Only shade if there are actual negative values
        if np.any(negative_vals < 0):
            zero_curve = pg.PlotDataItem(x, zero_line)
            neg_curve = pg.PlotDataItem(x, negative_vals)
            zero_curve.setClipToView(True)
            neg_curve.setClipToView(True)

            fill = pg.FillBetweenItem(
                neg_curve, zero_curve,
                brush=(255, 60, 60, 60),
            )
            self.plot_item.addItem(fill)
            self._fill_items.append(fill)

    # -- Mouse Events ---------------------------------------------------------

    def _on_mouse_move(self, ev):
        if self._values is None or len(self._values) == 0:
            return

        mouse_pos = ev.pos()
        scene_pos = self.mapToScene(mouse_pos)
        vb_rect = self.view_box.sceneBoundingRect()

        if not vb_rect.contains(scene_pos):
            self._hide_interactive()
            return

        view_pos = self.view_box.mapSceneToView(scene_pos)

        # Update crosshair
        if self._show_crosshair:
            self._crosshair_v.setPos(view_pos.x())
            self._crosshair_h.setPos(view_pos.y())
            self._crosshair_v.setVisible(True)
            self._crosshair_h.setVisible(True)

        # Update overlay
        self._overlay.update(mouse_pos)

    def _on_mouse_leave(self, ev):
        self._hide_interactive()

    def _hide_interactive(self):
        if self._crosshair_v:
            self._crosshair_v.setVisible(False)
        if self._crosshair_h:
            self._crosshair_h.setVisible(False)
        self._overlay.hide()

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

        # Update line color if using theme default
        if self._line_item is not None and not self._show_crosshair:
            pass  # Line color update handled on next update_data call

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
