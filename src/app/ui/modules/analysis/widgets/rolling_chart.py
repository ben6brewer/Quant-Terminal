"""Rolling Chart Widget - Line chart for rolling correlation/covariance."""

from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.date_index_axis import DraggableIndexDateAxisItem
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem
from app.ui.widgets.charting.overlays.crosshair_overlay import CrosshairOverlay


class RollingChart(BaseChart):
    """Chart for displaying rolling correlation or covariance time series.

    Args:
        mode: "correlation" or "covariance" — controls y-axis label and range.
    """

    def __init__(self, mode: str = "correlation", parent=None):
        self._placeholder = None  # Must exist before super().__init__ triggers resizeEvent
        super().__init__(parent=parent)
        self._mode = mode

        # Data storage for crosshair snapping
        self._dates: Optional[np.ndarray] = None
        self._values: Optional[np.ndarray] = None
        self._date_labels: list = []

        # Settings
        self._show_gridlines = True
        self._show_reference_lines = True
        self._show_crosshair = True
        self._line_width = 2
        self._line_color = None  # None = use theme accent
        self._line_style = Qt.SolidLine

        # Plot items
        self._line_item = None
        self._ref_lines = []

        self._setup_plots()
        self._setup_crosshair()
        self._setup_overlay()
        self._setup_placeholder()

    def _setup_plots(self):
        """Create plot item with custom axes (Y-axis on right, like chart module)."""
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

        # Hide default left axis, show right axis
        self.plot_item.showAxis("left", False)
        self.plot_item.showAxis("right", True)

        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

    def _setup_crosshair(self):
        """Create crosshair lines."""
        self._crosshair_v, self._crosshair_h = self._create_crosshair(
            self.plot_item, self.view_box
        )
        self.setMouseTracking(True)

    def _setup_overlay(self):
        """Create the axis overlay for value/date labels."""
        fmt = (lambda v: f"{v:.4f}") if self._mode == "correlation" else (lambda v: f"{v:.6f}")
        self._overlay = CrosshairOverlay(
            chart=self,
            plot_item=self.plot_item,
            view_box=self.view_box,
            value_formatter=fmt,
        )

    def _setup_placeholder(self):
        """Create a placeholder label shown when no data is loaded."""
        self._placeholder = QLabel("Enter two tickers and click Run", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Enter two tickers and click Run"):
        """Show placeholder message, hide chart."""
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
        self._ref_lines = []
        self._overlay.set_data([], 0)

    def plot_rolling_data(self, dates: np.ndarray, values: np.ndarray, settings: dict):
        """Plot rolling correlation/covariance data.

        Args:
            dates: numpy datetime64 array
            values: numpy float64 array
            settings: dict with display and line settings
        """
        import pandas as pd

        self._placeholder.setVisible(False)

        # Store data for crosshair
        self._dates = dates
        self._values = values
        self._date_labels = [
            pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates
        ]

        # Apply settings
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_reference_lines = settings.get("show_reference_lines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._line_width = settings.get("line_width", 2)
        self._line_color = settings.get("line_color", None)
        self._line_style = settings.get("line_style", Qt.SolidLine)

        show_value = settings.get("show_value_label", True)
        show_date = settings.get("show_date_label", True)

        # Update overlay data and visibility
        self._overlay.set_data(self._date_labels, len(values))
        self._overlay.set_visible(show_value, show_date)

        # Clear and redraw
        self.plot_item.clear()
        self._ref_lines = []
        self._setup_crosshair()

        # Set date index for bottom axis
        dt_index = pd.DatetimeIndex(dates)
        self._bottom_axis.set_index(dt_index)

        # Plot line
        x = np.arange(len(values))
        line_color = self._line_color if self._line_color else self._get_theme_accent_color()
        pen = pg.mkPen(color=line_color, width=self._line_width, style=self._line_style)
        self._line_item = self.plot_item.plot(x, values, pen=pen)
        self._line_item.setClipToView(True)

        # Reference lines
        if self._show_reference_lines:
            ref_color = self._get_crosshair_color()
            ref_pen = pg.mkPen(color=ref_color, width=1, style=Qt.DashLine)

            # y=0 line (both modes)
            zero_line = pg.InfiniteLine(pos=0, angle=0, pen=ref_pen)
            self.plot_item.addItem(zero_line, ignoreBounds=True)
            self._ref_lines.append(zero_line)

            # y=±1 lines (correlation only)
            if self._mode == "correlation":
                plus_one = pg.InfiniteLine(pos=1.0, angle=0, pen=ref_pen)
                minus_one = pg.InfiniteLine(pos=-1.0, angle=0, pen=ref_pen)
                self.plot_item.addItem(plus_one, ignoreBounds=True)
                self.plot_item.addItem(minus_one, ignoreBounds=True)
                self._ref_lines.extend([plus_one, minus_one])

        # Y-axis range
        if self._mode == "correlation":
            self.plot_item.setYRange(-1.05, 1.05, padding=0)
        else:
            y_min, y_max = float(np.nanmin(values)), float(np.nanmax(values))
            y_range = y_max - y_min if y_max != y_min else abs(y_max) or 1.0
            padding = y_range * 0.08
            self.plot_item.setYRange(y_min - padding, y_max + padding, padding=0)

        # X range
        self.plot_item.setXRange(0, len(values) - 1, padding=0.02)

        # Gridlines
        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )

    # ── Mouse Events ─────────────────────────────────────────────────

    def _on_mouse_move(self, ev):
        """Update crosshair lines and axis overlays on mouse move."""
        if self._values is None or len(self._values) == 0:
            return

        mouse_pos = ev.pos()

        # Map to view coords for crosshair snapping
        scene_pos = self.mapToScene(mouse_pos)
        vb_rect = self.view_box.sceneBoundingRect()

        if not vb_rect.contains(scene_pos):
            self._hide_interactive()
            return

        view_pos = self.view_box.mapSceneToView(scene_pos)
        idx = int(max(0, min(round(view_pos.x()), len(self._values) - 1)))

        # Update crosshair lines
        if self._show_crosshair:
            self._crosshair_v.setPos(idx)
            self._crosshair_h.setPos(self._values[idx])
            self._crosshair_v.setVisible(True)
            self._crosshair_h.setVisible(True)

        # Update axis overlay labels
        self._overlay.update(mouse_pos)

    def _on_mouse_leave(self, ev):
        """Hide interactive elements on mouse leave."""
        self._hide_interactive()

    def _hide_interactive(self):
        """Hide crosshair and overlay labels."""
        if self._crosshair_v:
            self._crosshair_v.setVisible(False)
        if self._crosshair_h:
            self._crosshair_h.setVisible(False)
        self._overlay.hide()

    # ── Theme ────────────────────────────────────────────────────────

    def _apply_gridlines(self):
        """Override base to respect the show_gridlines setting."""
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
        """Apply theme and update all visual elements."""
        super().set_theme(theme)

        # Update overlay label styles
        self._overlay.update_theme()

        # Update reference line colors
        if self._ref_lines:
            ref_color = self._get_crosshair_color()
            ref_pen = pg.mkPen(color=ref_color, width=1, style=Qt.DashLine)
            for line in self._ref_lines:
                line.setPen(ref_pen)

        # Update line color (only if using theme default)
        if self._line_item is not None and not self._line_color:
            accent = self._get_theme_accent_color()
            pen = pg.mkPen(color=accent, width=self._line_width, style=self._line_style)
            self._line_item.setPen(pen)

        # Update placeholder
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )

        # Update axis label/tick colors
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
