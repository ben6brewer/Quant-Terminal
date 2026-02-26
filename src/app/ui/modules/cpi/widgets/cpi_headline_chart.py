"""CPI Headline Chart - Line chart showing Headline CPI YoY% with crosshair overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

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


class CpiHeadlineChart(BaseChart):
    """Headline CPI YoY% line chart with right-side Y-axis and crosshair overlay."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

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
        self._overlay = CrosshairOverlay(
            chart=self,
            plot_item=self.plot_item,
            view_box=self.view_box,
            value_formatter=lambda v: f"{v:.2f}%",
        )

    def _setup_placeholder(self):
        """Create a placeholder label shown when no data is loaded."""
        self._placeholder = QLabel("Loading CPI data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading CPI data..."):
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

    def update_data(self, yoy_df: "pd.DataFrame", settings: dict):
        """Plot headline CPI YoY% line.

        Args:
            yoy_df: DataFrame with DatetimeIndex and "Headline CPI" column.
            settings: dict with display and line settings.
        """
        import pandas as pd

        if yoy_df is None or yoy_df.empty or "Headline CPI" not in yoy_df.columns:
            self.show_placeholder("No CPI data available.")
            return

        headline = yoy_df["Headline CPI"].dropna()
        if headline.empty:
            self.show_placeholder("No CPI data available.")
            return

        self._placeholder.setVisible(False)

        # Store data for crosshair
        self._dates = headline.index.values
        self._values = headline.values.astype(float)
        self._date_labels = [
            pd.Timestamp(d).strftime("%Y-%m-%d") for d in self._dates
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
        self._overlay.set_data(self._date_labels, len(self._values))
        self._overlay.set_visible(show_value, show_date)

        # Clear and redraw
        self.plot_item.clear()
        self._ref_lines = []
        self._setup_crosshair()

        # Set date index for bottom axis
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)

        # Plot line
        x = np.arange(len(self._values))
        line_color = self._line_color if self._line_color else self._get_theme_accent_color()
        pen = pg.mkPen(color=line_color, width=self._line_width, style=self._line_style)
        self._line_item = self.plot_item.plot(x, self._values, pen=pen)
        self._line_item.setClipToView(True)

        # Reference line: Fed 2% target
        if self._show_reference_lines:
            ref_pen = pg.mkPen(color=(255, 80, 80), width=1.5, style=Qt.DashLine)
            target_line = pg.InfiniteLine(
                pos=2.0,
                angle=0,
                pen=ref_pen,
                label="Fed Target: 2%",
                labelOpts={
                    "color": (255, 80, 80),
                    "position": 0.05,
                    "fill": None,
                },
            )
            self.plot_item.addItem(target_line, ignoreBounds=True)
            self._ref_lines.append(target_line)

        # Y-axis range
        y_min, y_max = float(np.nanmin(self._values)), float(np.nanmax(self._values))
        y_range = y_max - y_min if y_max != y_min else abs(y_max) or 1.0
        padding = y_range * 0.08
        self.plot_item.setYRange(y_min - padding, y_max + padding, padding=0)

        # X range
        self.plot_item.setXRange(0, len(self._values) - 1, padding=0.02)

        # Gridlines
        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )

    # -- Mouse Events ---------------------------------------------------------

    def _on_mouse_move(self, ev):
        """Update crosshair lines and axis overlays on mouse move."""
        if self._values is None or len(self._values) == 0:
            return

        mouse_pos = ev.pos()
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

    # -- Theme ----------------------------------------------------------------

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

        # Update reference line colors (Fed target stays red)
        # No color change needed for Fed target — it's always red

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
