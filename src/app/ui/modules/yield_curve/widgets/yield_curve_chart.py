"""Yield Curve Chart Widget - PyQtGraph chart with tenor axis and crosshair."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu, QFileDialog, QApplication
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from app.ui.widgets.charting.axes import DraggableAxisItem

from ..services.fred_service import TENOR_LABELS, TENOR_YEARS


def _tenor_transform(x: float) -> float:
    """Map real years to display x using power scaling (Bloomberg-style)."""
    return x ** 0.6


# Pre-compute display x for each tenor (used by axis + plotting)
TENOR_DISPLAY_X: Dict[str, float] = {
    label: _tenor_transform(years) for label, years in TENOR_YEARS.items()
}

# Colors for curve lines (today + up to 7 overlays)
CURVE_COLORS = [
    (0, 212, 255),    # Cyan (today / accent)
    (255, 150, 0),    # Orange
    (0, 255, 150),    # Green
    (150, 0, 255),    # Purple
    (255, 200, 0),    # Yellow
    (255, 0, 150),    # Pink
    (100, 200, 255),  # Light blue
    (255, 100, 100),  # Light red
]

# Bloomberg theme overrides first color to orange accent
CURVE_COLORS_BLOOMBERG = [
    (255, 128, 0),    # Bloomberg orange (today / accent)
    (0, 212, 255),    # Cyan
    (0, 255, 150),    # Green
    (150, 0, 255),    # Purple
    (255, 200, 0),    # Yellow
    (255, 0, 150),    # Pink
    (100, 200, 255),  # Light blue
    (255, 100, 100),  # Light red
]


@dataclass
class CurveData:
    """Data for a single yield curve to plot."""

    label: str  # Legend label (e.g., "2026-02-07" or "Today")
    maturities: List[float]  # Raw tenor maturities in years
    yields: List[float]  # Raw yield values in percent
    smooth_x: List[float]  # Interpolated x values
    smooth_y: List[float]  # Interpolated y values
    color_index: int = 0  # Index into CURVE_COLORS


class TenorAxisItem(DraggableAxisItem):
    """Custom X-axis that maps sqrt-transformed positions to tenor labels."""

    # Map from transformed display-x to tenor label
    TICK_MAP: Dict[float, str] = {dx: label for label, dx in TENOR_DISPLAY_X.items()}

    def __init__(self, orientation: str = "bottom", *args, **kwargs):
        super().__init__(orientation=orientation, *args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        """Convert transformed x values to tenor labels."""
        strings = []
        for v in values:
            best_label = ""
            best_dist = float("inf")
            for display_x, label in self.TICK_MAP.items():
                dist = abs(v - display_x)
                if dist < best_dist:
                    best_dist = dist
                    best_label = label
            # Threshold tighter because sqrt positions are closer together
            if best_dist < 0.05:
                strings.append(best_label)
            else:
                strings.append("")
        return strings

    def tickValues(self, minVal, maxVal, size):
        """Generate tick positions at transformed tenor values."""
        ticks = []
        major_ticks = []
        for display_x in TENOR_DISPLAY_X.values():
            if minVal <= display_x <= maxVal:
                major_ticks.append(display_x)

        if major_ticks:
            ticks.append((1, major_ticks))

        return ticks


class YieldCurveChart(LazyThemeMixin, QWidget):
    """
    Yield curve chart with smooth interpolated lines and scatter dots.

    Uses PyQtGraph for rendering with custom TenorAxisItem for X-axis
    and DraggableAxisItem for Y-axis.
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        # Crosshair lines
        self._crosshair_v: Optional[pg.InfiniteLine] = None
        self._crosshair_h: Optional[pg.InfiniteLine] = None

        # Plot items for clearing
        self._plot_items: List = []

        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup chart layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # PyQtGraph widget
        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget, stretch=1)

        # Custom axes
        self._bottom_axis = TenorAxisItem(orientation="bottom")
        self._left_axis = DraggableAxisItem(orientation="left")

        # Create plot item
        self.plot_item = self.plot_widget.addPlot(
            axisItems={
                "bottom": self._bottom_axis,
                "left": self._left_axis,
            }
        )
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.setLabel("left", "Yield (%)")

        # Set left axis width
        self._left_axis.setWidth(55)

        # ViewBox
        self._view_box = self.plot_item.getViewBox()
        self._view_box.setMouseEnabled(x=True, y=True)
        self._view_box.setMenuEnabled(False)

        # Legend
        self.legend = self.plot_item.addLegend(offset=(60, 5))
        self.legend.setParentItem(self.plot_item.graphicsItem())

        # Mouse tracking for crosshair
        self.setMouseTracking(True)
        self.plot_widget.setMouseTracking(True)
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Placeholder
        self.placeholder = QLabel("Loading yield curve data...")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("font-size: 16px; color: #888888;")
        layout.addWidget(self.placeholder)
        self.placeholder.setVisible(True)
        self.plot_widget.setVisible(False)

    def plot_curves(self, curves: List[CurveData]) -> None:
        """
        Clear and redraw all yield curves.

        Args:
            curves: List of CurveData to plot. First is "today", rest are overlays.
        """
        self._clear_plot()

        if not curves:
            self.show_placeholder("No yield curve data available")
            return

        self.placeholder.setVisible(False)
        self.plot_widget.setVisible(True)

        theme = self.theme_manager.current_theme
        colors = CURVE_COLORS_BLOOMBERG if theme == "bloomberg" else CURVE_COLORS

        for curve in curves:
            color = colors[curve.color_index % len(colors)]
            pen = pg.mkPen(color=color, width=2)

            # Transform x-coordinates from real years to sqrt-scaled display space
            display_smooth_x = [_tenor_transform(x) for x in curve.smooth_x]
            display_maturities = [_tenor_transform(x) for x in curve.maturities]

            # Smooth interpolated line
            line = self.plot_item.plot(
                display_smooth_x, curve.smooth_y,
                pen=pen, name=curve.label,
            )
            line.setClipToView(True)
            self._plot_items.append(line)

            # Scatter dots at raw data points
            scatter = pg.ScatterPlotItem(
                display_maturities, curve.yields,
                pen=pg.mkPen(color, width=1),
                brush=pg.mkBrush(*color, 200),
                size=8,
            )
            self.plot_item.addItem(scatter)
            self._plot_items.append(scatter)

        self.plot_item.autoRange()

    def _clear_plot(self):
        """Remove all plot items and clear legend."""
        for item in self._plot_items:
            self.plot_item.removeItem(item)
        self._plot_items.clear()
        self.legend.clear()

    def show_placeholder(self, message: str):
        """Show placeholder message, hide chart."""
        self._clear_plot()
        self.placeholder.setText(message)
        self.placeholder.setVisible(True)
        self.plot_widget.setVisible(False)

    # ========== Crosshair ==========

    def _create_crosshair(self):
        """Create crosshair lines if not already created."""
        if self._crosshair_v is not None:
            return

        color = self._get_crosshair_color()
        pen = pg.mkPen(color=color, width=1, style=Qt.DashLine)

        self._crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pen)

        self._view_box.addItem(self._crosshair_v)
        self._view_box.addItem(self._crosshair_h)

        self._crosshair_v.hide()
        self._crosshair_h.hide()

    def _get_crosshair_color(self) -> Tuple[int, int, int]:
        theme = self.theme_manager.current_theme
        if theme == "light":
            return (100, 100, 100)
        elif theme == "bloomberg":
            return (100, 120, 140)
        return (150, 150, 150)

    def _on_mouse_moved(self, scene_pos):
        if not self.plot_widget.isVisible():
            return

        vb_rect = self._view_box.sceneBoundingRect()
        if not vb_rect.contains(scene_pos):
            self._hide_crosshair()
            return

        view_pos = self._view_box.mapSceneToView(scene_pos)

        self._create_crosshair()
        if self._crosshair_v and self._crosshair_h:
            self._crosshair_v.setPos(view_pos.x())
            self._crosshair_h.setPos(view_pos.y())
            self._crosshair_v.show()
            self._crosshair_h.show()

    def _hide_crosshair(self):
        if self._crosshair_v:
            self._crosshair_v.hide()
        if self._crosshair_h:
            self._crosshair_h.hide()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hide_crosshair()

    # ========== Context Menu ==========

    def contextMenuEvent(self, event):
        """Show right-click context menu with export options."""
        from app.services.theme_stylesheet_service import ThemeStylesheetService

        menu = QMenu(self)

        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['accent']};
                padding: 4px;
            }}
            QMenu::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
            }}
        """)

        copy_action = menu.addAction("Copy to Clipboard")
        save_action = menu.addAction("Save as PNG...")

        action = menu.exec(event.globalPos())
        if action == copy_action:
            QApplication.clipboard().setPixmap(self.grab())
        elif action == save_action:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Chart as PNG", "", "PNG Files (*.png)"
            )
            if path:
                self.grab().save(path, "PNG")

    # ========== Theme ==========

    def _apply_theme(self):
        """Apply theme styling."""
        theme = self.theme_manager.current_theme

        if theme == "dark":
            bg_rgb = (30, 30, 30)
            text_color = "#ffffff"
            grid_color = (80, 80, 80)
        elif theme == "light":
            bg_rgb = (255, 255, 255)
            text_color = "#000000"
            grid_color = (200, 200, 200)
        else:  # bloomberg
            bg_rgb = (13, 20, 32)
            text_color = "#e8e8e8"
            grid_color = (50, 60, 80)

        self.plot_widget.setBackground(bg_rgb)

        axis_pen = pg.mkPen(color=grid_color, width=1)
        for axis_name in ("bottom", "left"):
            axis = self.plot_item.getAxis(axis_name)
            axis.setPen(axis_pen)
            axis.setTextPen(text_color)

        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        # Legend styling
        self.legend.setLabelTextColor(text_color)
        self.legend.setBrush(pg.mkBrush(None))
        self.legend.setPen(pg.mkPen(None))

        self.placeholder.setStyleSheet(
            f"font-size: 16px; color: #888888; background: transparent;"
        )
        self.setStyleSheet(f"background-color: rgb{bg_rgb};")

        # Update crosshair color
        if self._crosshair_v is not None:
            color = self._get_crosshair_color()
            pen = pg.mkPen(color=color, width=1, style=Qt.DashLine)
            self._crosshair_v.setPen(pen)
            self._crosshair_h.setPen(pen)
