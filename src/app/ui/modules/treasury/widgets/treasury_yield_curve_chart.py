"""Treasury Yield Curve Chart - Snapshot curve with overlay support via CurveData."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem

from ..services.treasury_fred_service import TENOR_LABELS, TENOR_YEARS


def _tenor_transform(x: float) -> float:
    """Map real years to display x using power scaling (Bloomberg-style)."""
    return x ** 0.6


# Pre-compute display x for each tenor
TENOR_DISPLAY_X: Dict[str, float] = {
    label: _tenor_transform(years) for label, years in TENOR_YEARS.items()
}

# Colors for curve lines (today + up to 7 overlays)
CURVE_COLORS = [
    None,              # Index 0 = theme accent (resolved at render time)
    (255, 150, 0),     # Orange
    (0, 255, 150),     # Green
    (150, 0, 255),     # Purple
    (255, 200, 0),     # Yellow
    (255, 0, 150),     # Pink
    (100, 200, 255),   # Light blue
    (255, 100, 100),   # Light red
]


@dataclass
class CurveData:
    """Data for a single yield curve to plot."""

    label: str                       # Legend label (e.g., "Today" or "2025-02-07")
    maturities: List[float]          # Raw tenor maturities in years
    yields: List[float]              # Raw yield values in percent
    smooth_x: List[float]            # Interpolated x values (years)
    smooth_y: List[float]            # Interpolated y values (percent)
    color_index: int = 0             # Index into CURVE_COLORS
    yields_dict: Optional[Dict[str, float]] = None  # tenor -> yield for tooltip


class _TenorAxisItem(DraggableAxisItem):
    """Custom X-axis that maps power-scaled positions to tenor labels."""

    TICK_MAP: Dict[float, str] = {dx: label for label, dx in TENOR_DISPLAY_X.items()}

    def __init__(self, orientation="bottom"):
        super().__init__(orientation=orientation)

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            best_label = ""
            best_dist = float("inf")
            for display_x, label in self.TICK_MAP.items():
                dist = abs(v - display_x)
                if dist < best_dist:
                    best_dist = dist
                    best_label = label
            if best_dist < 0.05:
                strings.append(best_label)
            else:
                strings.append("")
        return strings

    def tickValues(self, minVal, maxVal, size):
        ticks = []
        major_ticks = []
        for display_x in TENOR_DISPLAY_X.values():
            if minVal <= display_x <= maxVal:
                major_ticks.append(display_x)
        if major_ticks:
            ticks.append((1, major_ticks))
        return ticks


class TreasuryYieldCurveChart(BaseChart):
    """Yield curve chart accepting pre-built CurveData objects from the module."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        # Settings (applied from module)
        self._show_gridlines = True
        self._show_crosshair = True

        # Plot items for clearing
        self._plot_items: list = []
        self._legend = None
        self._curve_data: List[Tuple[str, Dict[str, float]]] = []

        self._setup_plots()
        self._setup_crosshair()
        self._setup_tooltip()
        self._setup_placeholder()

    def _setup_plots(self):
        self._bottom_axis = _TenorAxisItem(orientation="bottom")
        self._left_axis = DraggableAxisItem(orientation="left")
        self._left_axis.setWidth(55)

        self.plot_item = self.addPlot(
            axisItems={
                "bottom": self._bottom_axis,
                "left": self._left_axis,
            }
        )
        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMouseEnabled(x=True, y=True)

        self.plot_item.setLabel("left", "Yield (%)")
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

    def _setup_crosshair(self):
        self._crosshair_v, self._crosshair_h = self._create_crosshair(
            self.plot_item, self.view_box
        )
        self.setMouseTracking(True)

    def _setup_tooltip(self):
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
        self._placeholder = QLabel("Loading yield curve...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading yield curve..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        self._clear_plot()

    # ---- Plotting -----------------------------------------------------------

    def plot_curves(
        self,
        curves: List[CurveData],
        settings: dict,
        fed_funds_rate: Optional[float] = None,
    ) -> None:
        """
        Clear and redraw all yield curves.

        Args:
            curves: Pre-built CurveData objects. First is "today", rest are overlays.
            settings: Display settings dict.
            fed_funds_rate: Optional Fed Funds rate for reference line.
        """
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        show_fed_funds = settings.get("show_fed_funds", True)

        self._clear_plot()

        if not curves:
            self.show_placeholder("No yield curve data available")
            return

        self._placeholder.setVisible(False)

        accent = self._get_theme_accent_color()

        # Legend
        self._legend = self.plot_item.addLegend(offset=(60, 5))
        self._legend.setBrush(pg.mkBrush(color=(0, 0, 0, 100)))

        self._curve_data = []

        for curve in curves:
            color = accent if curve.color_index == 0 else CURVE_COLORS[
                min(curve.color_index, len(CURVE_COLORS) - 1)
            ]
            width = 3 if curve.color_index == 0 else 2
            style = Qt.SolidLine if curve.color_index == 0 else Qt.DashLine

            # Transform x-coordinates to display space
            display_smooth_x = [_tenor_transform(x) for x in curve.smooth_x]
            display_maturities = [_tenor_transform(x) for x in curve.maturities]

            pen = pg.mkPen(color=color, width=width, style=style)
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
                brush=pg.mkBrush(*(color if isinstance(color, tuple) else accent), 200),
                size=8 if curve.color_index == 0 else 6,
            )
            self.plot_item.addItem(scatter)
            self._plot_items.append(scatter)

            # Store for tooltip
            if curve.yields_dict:
                self._curve_data.append((curve.label, curve.yields_dict))

        # Fed funds reference line
        if show_fed_funds and fed_funds_rate is not None:
            ref_pen = pg.mkPen(color=(255, 80, 80), width=1.5, style=Qt.DashLine)
            ff_line = pg.InfiniteLine(
                pos=fed_funds_rate, angle=0, pen=ref_pen,
                label=f"Fed Funds: {fed_funds_rate:.2f}%",
                labelOpts={"color": (255, 80, 80), "position": 0.05, "fill": None},
            )
            self.plot_item.addItem(ff_line, ignoreBounds=True)
            self._plot_items.append(ff_line)

        # Gridlines
        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )

        self.plot_item.autoRange()

    def _clear_plot(self):
        for item in self._plot_items:
            self.plot_item.removeItem(item)
        self._plot_items.clear()
        self._curve_data.clear()
        if self._legend is not None:
            self._legend.clear()
            self._legend.scene().removeItem(self._legend)
            self.plot_item.legend = None
            self._legend = None

    # ---- Mouse Events -------------------------------------------------------

    def _on_mouse_move(self, ev):
        if not self._curve_data:
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

        # Find nearest tenor
        display_x = view_pos.x()
        best_tenor = None
        best_dist = float("inf")
        for tenor, dx in TENOR_DISPLAY_X.items():
            dist = abs(display_x - dx)
            if dist < best_dist:
                best_dist = dist
                best_tenor = tenor

        if best_tenor is None or best_dist > 0.3:
            self._tooltip.setVisible(False)
            return

        # Build tooltip
        lines = [f"<b>{best_tenor}</b>"]
        for label, yields_dict in self._curve_data:
            if best_tenor in yields_dict:
                val = yields_dict[best_tenor]
                lines.append(f"{label}: <b>{val:.3f}%</b>")

        self._tooltip.setText("<br>".join(lines))
        self._tooltip.adjustSize()

        # Position tooltip
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
        self._tooltip.setVisible(False)

    # ---- Theme --------------------------------------------------------------

    def _apply_gridlines(self):
        if self.plot_item is None:
            return
        grid_color = self._get_contrasting_grid_color()
        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )
        self.plot_item.getAxis('bottom').setPen(color=grid_color, width=1)
        self.plot_item.getAxis('left').setPen(color=grid_color, width=1)

    def set_theme(self, theme: str):
        super().set_theme(theme)
        self._apply_tooltip_style()

        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )

        text_color = self._get_label_text_color()
        for axis_name in ("bottom", "left"):
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
