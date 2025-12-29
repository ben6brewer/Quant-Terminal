"""
Draggable oscillator pane widget for displaying technical indicators.

Each pane is a self-contained QGraphicsWidget with:
- Independent PlotItem with ViewBox for oscillator data
- Dedicated y-axis (right-aligned)
- Title bar for dragging
- Theme-aware styling
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import QGraphicsWidget, QGraphicsRectItem, QGraphicsTextItem


class OscillatorPane(QGraphicsWidget):
    """
    A draggable oscillator pane that overlays the price chart.

    Features:
    - Independent PlotItem with ViewBox for oscillator data
    - Dedicated y-axis (right-aligned, moves with pane)
    - Draggable via title bar
    - Auto-fit y-range to data
    - Theme-aware styling
    """

    def __init__(
        self,
        indicator_name: str,
        pane_id: int,
        theme_manager,
        parent=None
    ):
        super().__init__(parent)

        self.indicator_name = indicator_name
        self.pane_id = pane_id
        self.theme_manager = theme_manager

        # Dimensions
        self.pane_width = 600
        self.pane_height = 150
        self.title_bar_height = 25
        self.axis_width = 80

        # Visual components (QGraphicsRectItem)
        self.background = None
        self.title_bar = None
        self.border = None
        self.title_text = None  # QGraphicsTextItem

        # PyQtGraph components
        self.plot_item = None
        self.view_box = None
        self.y_axis = None

        # Data
        self.indicator_lines = []  # PlotCurveItem / ScatterPlotItem

        # Dragging state
        self._is_dragging = False
        self._drag_start_pos = None

        self._create_ui()
        self.setAcceptHoverEvents(True)

    def _create_ui(self):
        """Create the visual structure of the pane."""
        # Background rectangle (fully transparent)
        self.background = QGraphicsRectItem(0, 0, self.pane_width, self.pane_height, self)
        self.background.setBrush(QBrush(QColor(0, 0, 0, 0)))  # Fully transparent
        self.background.setPen(QPen(Qt.NoPen))

        # Title bar (drag handle) - semi-transparent
        self.title_bar = QGraphicsRectItem(0, 0, self.pane_width, self.title_bar_height, self)
        self.title_bar.setBrush(QBrush(QColor(30, 30, 30, 200)))  # Semi-transparent
        self.title_bar.setPen(QPen(Qt.NoPen))

        # Title text
        self.title_text = QGraphicsTextItem(self.indicator_name, self)
        self.title_text.setPos(5, 2)
        self.title_text.setDefaultTextColor(QColor(255, 255, 255))

        # Set smaller font for title
        font = self.title_text.font()
        font.setPointSize(9)
        font.setBold(True)
        self.title_text.setFont(font)

        # PlotItem with right y-axis (simpler approach)
        from app.ui.widgets.price_chart import DraggableAxisItem

        self.plot_item = pg.PlotItem(
            axisItems={'right': DraggableAxisItem(orientation='right')}
        )
        self.plot_item.setParentItem(self)

        # Position plot below title bar, reserve space for axis
        plot_width = self.pane_width - self.axis_width
        plot_height = self.pane_height - self.title_bar_height
        self.plot_item.setGeometry(0, self.title_bar_height, plot_width, plot_height)

        # Get ViewBox and axis references
        self.view_box = self.plot_item.getViewBox()
        self.y_axis = self.plot_item.getAxis('right')

        # Configure axes visibility
        self.plot_item.showAxis('right')
        self.plot_item.hideAxis('left')
        self.plot_item.hideAxis('bottom')
        self.plot_item.hideAxis('top')

        # Remove ViewBox border by setting transparent pen
        self.view_box.setBorder(pg.mkPen(None))

        # Disable auto-range (we'll manage it manually)
        self.view_box.enableAutoRange(enable=False)

        # No border outline for the pane
        self.border = None

    def set_data(
        self,
        x: np.ndarray,
        indicator_df: pd.DataFrame,
        per_line_appearance: dict
    ) -> None:
        """
        Render oscillator data.

        Args:
            x: X-axis values (typically date indices)
            indicator_df: DataFrame with indicator columns
            per_line_appearance: Dict mapping column names to appearance settings
        """
        # Clear existing data
        self.clear_data()

        # Plot each column
        for col in indicator_df.columns:
            line_settings = per_line_appearance.get(col, {})

            if not line_settings.get("visible", True):
                continue

            y_series = indicator_df[col]

            # Check if sparse signal (e.g., crossover markers)
            non_nan_count = y_series.notna().sum()
            is_sparse = non_nan_count < (len(y_series) * 0.1)

            if is_sparse and non_nan_count > 0:
                # Scatter plot for crossovers
                mask = y_series.notna()
                scatter = pg.ScatterPlotItem(
                    x=x[mask],
                    y=y_series[mask].to_numpy(),
                    pen=pg.mkPen(None),
                    brush=pg.mkBrush(line_settings.get("color", (0, 150, 255))),
                    symbol=line_settings.get("marker_shape", "o"),
                    size=line_settings.get("marker_size", 10)
                )
                self.view_box.addItem(scatter)
                self.indicator_lines.append(scatter)
            else:
                # Line plot for continuous indicators
                pen = pg.mkPen(
                    color=line_settings.get("color", (0, 150, 255)),
                    width=line_settings.get("line_width", 2),
                    style=line_settings.get("line_style", Qt.SolidLine)
                )
                line = pg.PlotCurveItem(x=x, y=y_series.to_numpy(), pen=pen)
                self.view_box.addItem(line)
                self.indicator_lines.append(line)

        # Auto-fit y-range
        self.auto_fit_y_range()

    def clear_data(self) -> None:
        """Clear all indicator lines from the pane."""
        for line in self.indicator_lines:
            self.view_box.removeItem(line)
        self.indicator_lines.clear()

    def auto_fit_y_range(self) -> None:
        """Auto-fit y-axis to data with padding."""
        if not self.indicator_lines:
            return

        all_y_values = []
        for item in self.indicator_lines:
            if isinstance(item, pg.ScatterPlotItem):
                points = item.getData()
                if points and len(points) > 1:
                    all_y_values.extend(points[1])
            elif isinstance(item, pg.PlotCurveItem):
                y_data = item.getData()[1]
                if y_data is not None:
                    all_y_values.extend(y_data[np.isfinite(y_data)])

        if all_y_values:
            y_min, y_max = np.min(all_y_values), np.max(all_y_values)

            # Add 10% padding
            padding = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
            self.view_box.setYRange(y_min - padding, y_max + padding, padding=0)

    def set_x_link(self, target_view_box) -> None:
        """
        Link X-axis to price chart for synchronized zoom/pan.

        Args:
            target_view_box: The price chart's ViewBox to link with
        """
        self.view_box.setXLink(target_view_box)

    def apply_theme(self, theme: str) -> None:
        """
        Update pane styling based on theme.

        Args:
            theme: Theme name ("dark", "light", "bloomberg")
        """
        if theme == "light":
            title_bg = QColor(224, 224, 224, 200)
            text_color = QColor(0, 0, 0)
        elif theme == "bloomberg":
            title_bg = QColor(10, 16, 24, 200)
            text_color = QColor(232, 232, 232)
        else:  # dark
            title_bg = QColor(30, 30, 30, 200)
            text_color = QColor(255, 255, 255)

        # Keep background fully transparent (don't update it)
        # Only update title bar and text
        self.title_bar.setBrush(QBrush(title_bg))
        self.title_text.setDefaultTextColor(text_color)

    def update_width(self, new_width: float) -> None:
        """
        Update pane width (called when chart is resized).

        Args:
            new_width: New width for the pane
        """
        self.pane_width = new_width

        # Update visual elements
        self.background.setRect(0, 0, self.pane_width, self.pane_height)
        self.title_bar.setRect(0, 0, self.pane_width, self.title_bar_height)

        # Update plot geometry (reserve space for axis)
        plot_width = self.pane_width - self.axis_width
        plot_height = self.pane_height - self.title_bar_height
        self.plot_item.setGeometry(0, self.title_bar_height, plot_width, plot_height)

    # -------------------------
    # Mouse Event Handlers
    # -------------------------

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.LeftButton:
            # Check if click is on title bar
            local_pos = self.mapFromScene(event.scenePos())
            if local_pos.y() <= self.title_bar_height:
                self._is_dragging = True
                self._drag_start_pos = event.scenePos()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if self._is_dragging:
            delta = event.scenePos() - self._drag_start_pos
            new_pos = self.pos() + delta
            self.setPos(new_pos)
            self._drag_start_pos = event.scenePos()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to end dragging."""
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        """Change cursor when hovering over title bar."""
        local_pos = self.mapFromScene(event.scenePos())
        if local_pos.y() <= self.title_bar_height:
            self.setCursor(Qt.SizeAllCursor)
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        """Update cursor based on position."""
        local_pos = self.mapFromScene(event.scenePos())
        if local_pos.y() <= self.title_bar_height:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """Reset cursor when leaving pane."""
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)
