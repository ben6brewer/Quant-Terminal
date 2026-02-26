"""CPI Component Breakdown Chart - Stacked area chart of CPI components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem

if TYPE_CHECKING:
    import pandas as pd

from ..services.cpi_fred_service import COMPONENT_LABELS, COMPONENT_WEIGHTS

# Stacking order: largest CPI weight first (Housing 40.4% → Apparel 2.5%)
STACK_ORDER = [
    "Housing", "Food & Beverages", "Transportation", "Medical Care",
    "Energy", "Education", "Recreation", "Apparel",
]

# Color palette keyed by component name
COMPONENT_COLORS: Dict[str, str] = {
    "Housing": "#66BB6A",
    "Food & Beverages": "#4FC3F7",
    "Transportation": "#AB47BC",
    "Medical Care": "#EF5350",
    "Energy": "#FF7043",
    "Education": "#26C6DA",
    "Recreation": "#EC407A",
    "Apparel": "#FFA726",
}


class _MonthAxisItem(pg.AxisItem):
    """Custom axis that maps integer indices to month label strings."""

    def __init__(self, orientation="bottom"):
        super().__init__(orientation)
        self._labels: List[str] = []

    def set_labels(self, labels: List[str]):
        self._labels = labels

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            idx = int(round(v))
            if 0 <= idx < len(self._labels):
                strings.append(self._labels[idx])
            else:
                strings.append("")
        return strings


class CpiComponentBreakdownChart(BaseChart):
    """Stacked area chart showing component contributions to headline CPI."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        # Settings
        self._show_gridlines = True
        self._show_reference_lines = True
        self._show_crosshair = True
        self._show_headline_overlay = True
        self._show_hover_tooltip = True

        # Plot items
        self._fill_items: list = []
        self._curve_items: list = []  # boundary curves + legend dummies
        self._ref_lines: list = []
        self._headline_line = None
        self._legend = None
        self._month_labels: List[str] = []

        # Contribution data for tooltip (set in update_data)
        self._contributions: Optional[List[List[tuple]]] = None
        self._headline_values: Optional[np.ndarray] = None
        self._n_months: int = 0

        self._setup_plots()
        self._setup_crosshair()
        self._setup_tooltip()
        self._setup_placeholder()

    def _setup_plots(self):
        """Create plot item with right-side Y-axis."""
        self._bottom_axis = _MonthAxisItem(orientation="bottom")
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

        self.plot_item.showGrid(x=False, y=True, alpha=0.3)

    def _setup_crosshair(self):
        """Create vertical crosshair line (no horizontal — stacked areas)."""
        color = self._get_crosshair_color()
        pen = pg.mkPen(color=color, width=1, style=Qt.DashLine)
        self._crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._crosshair_v.setVisible(False)
        self.plot_item.addItem(self._crosshair_v, ignoreBounds=True)
        self.setMouseTracking(True)

    def _setup_tooltip(self):
        """Create the floating tooltip label."""
        self._tooltip = QLabel(self)
        self._tooltip.setVisible(False)
        self._tooltip.setWordWrap(False)
        self._tooltip.setTextFormat(Qt.RichText)
        self._apply_tooltip_style()

    def _apply_tooltip_style(self):
        """Apply theme-aware styling to the tooltip."""
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
        """Create a placeholder label shown when no data is loaded."""
        self._placeholder = QLabel("Loading component data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading component data..."):
        """Show placeholder message, hide chart."""
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        self._clear_plot()

    def _clear_plot(self):
        """Remove all plot items."""
        for item in self._fill_items:
            self.plot_item.removeItem(item)
        self._fill_items.clear()

        for item in self._curve_items:
            self.plot_item.removeItem(item)
        self._curve_items.clear()

        for item in self._ref_lines:
            self.plot_item.removeItem(item)
        self._ref_lines.clear()

        if self._headline_line is not None:
            self.plot_item.removeItem(self._headline_line)
            self._headline_line = None

        if self._legend is not None:
            self._legend.clear()
            self._legend.scene().removeItem(self._legend)
            self.plot_item.legend = None
            self._legend = None

        self._month_labels.clear()
        self._contributions = None
        self._headline_values = None
        self._n_months = 0

    def update_data(self, yoy_df: "pd.DataFrame", settings: dict):
        """Plot stacked area chart for component data.

        Args:
            yoy_df: DataFrame with DatetimeIndex and component columns.
            settings: dict with display settings.
        """
        self.setUpdatesEnabled(False)
        try:
            self._update_data_inner(yoy_df, settings)
        finally:
            self.setUpdatesEnabled(True)

    def _update_data_inner(self, yoy_df: "pd.DataFrame", settings: dict):
        """Inner implementation of update_data (called with updates disabled)."""
        self._clear_plot()

        if yoy_df is None or yoy_df.empty:
            self.show_placeholder("No component data available.")
            return

        # Filter to only component columns that exist
        available = [c for c in COMPONENT_LABELS if c in yoy_df.columns]
        if not available:
            self.show_placeholder("No component data available.")
            return

        # Drop rows where all components are NaN
        component_df = yoy_df[available].dropna(how="all")
        if component_df.empty:
            self.show_placeholder("Insufficient component data.")
            return

        # Get headline values
        headline_values = None
        if "Headline CPI" in yoy_df.columns:
            headline_slice = yoy_df.loc[component_df.index, "Headline CPI"]
            headline_values = headline_slice.values

        self._placeholder.setVisible(False)

        # Apply settings
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_reference_lines = settings.get("show_reference_lines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_headline_overlay = settings.get("show_headline_overlay", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)

        n_months = len(component_df)
        self._n_months = n_months

        # Month labels for x-axis
        self._month_labels = [dt.strftime("%b '%y") for dt in component_df.index]
        self._bottom_axis.set_labels(self._month_labels)

        # Pre-compute weighted contributions so areas sum to headline CPI
        contributions: List[List[tuple]] = []
        for month_idx in range(n_months):
            headline = headline_values[month_idx] if headline_values is not None else np.nan

            raw = {}
            for comp_name in available:
                val = component_df.iloc[month_idx][comp_name]
                if np.isnan(val):
                    continue
                w = COMPONENT_WEIGHTS.get(comp_name, 0.0)
                raw[comp_name] = w * val

            raw_sum = sum(raw.values())

            if not np.isnan(headline) and raw_sum != 0:
                scale = headline / raw_sum
            elif np.isnan(headline):
                scale = 1.0
            else:
                scale = 0.0

            month_contribs = []
            for comp_name in available:
                if comp_name in raw:
                    month_contribs.append((comp_name, raw[comp_name] * scale))

            contributions.append(month_contribs)

        self._contributions = contributions
        self._headline_values = headline_values

        # Build stacked area fills using FillBetweenItem
        self._build_stacked_areas(n_months, contributions)

        # Headline CPI overlay line
        if self._show_headline_overlay and headline_values is not None:
            self._add_headline_line(n_months, headline_values)

        # Fed 2% target reference line
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

        # Legend
        if self._show_legend:
            self._add_legend()

        # Gridlines
        self.plot_item.showGrid(x=False, y=self._show_gridlines, alpha=0.3)

        self.plot_item.autoRange()

    def _build_stacked_areas(self, n_months: int, contributions: List[List[tuple]]):
        """Build FillBetweenItem stacked areas for each component."""
        x = np.arange(n_months, dtype=float)

        # Build per-component contribution arrays in stack order
        # Only include components that appear in contributions
        present_components = set()
        for month_contribs in contributions:
            for comp_name, _ in month_contribs:
                present_components.add(comp_name)

        ordered = [c for c in STACK_ORDER if c in present_components]

        # Build value arrays for each component
        comp_values: Dict[str, np.ndarray] = {}
        for comp_name in ordered:
            arr = np.zeros(n_months)
            for month_idx, month_contribs in enumerate(contributions):
                for name, val in month_contribs:
                    if name == comp_name:
                        arr[month_idx] = val
                        break
            comp_values[comp_name] = arr

        # Stack cumulatively
        cumulative = np.zeros(n_months)

        for comp_name in ordered:
            values = comp_values[comp_name]
            lower = cumulative.copy()
            upper = cumulative + values

            color_hex = COMPONENT_COLORS.get(comp_name, "#888888")
            color = QColor(color_hex)
            brush_color = (color.red(), color.green(), color.blue(), 160)

            lower_curve = pg.PlotDataItem(x, lower)
            upper_curve = pg.PlotDataItem(x, upper)
            lower_curve.setClipToView(True)
            upper_curve.setClipToView(True)

            fill = pg.FillBetweenItem(lower_curve, upper_curve, brush=brush_color)
            self.plot_item.addItem(fill)
            self._fill_items.append(fill)
            self._curve_items.extend([lower_curve, upper_curve])

            cumulative = upper

    def _add_headline_line(self, n_months: int, headline_values: np.ndarray):
        """Add bold accent-colored headline CPI line on top of the stack."""
        x = []
        y = []
        for i, val in enumerate(headline_values):
            if not np.isnan(val):
                x.append(i)
                y.append(val)
        if len(x) > 1:
            accent = self._get_theme_accent_color()
            pen = pg.mkPen(color=accent, width=2.5)
            self._headline_line = self.plot_item.plot(x, y, pen=pen)

    def _add_legend(self):
        """Add a pyqtgraph legend showing component colors."""
        self._legend = self.plot_item.addLegend(offset=(60, 10))
        self._legend.setBrush(pg.mkBrush(color=(0, 0, 0, 100)))

        # Add dummy PlotDataItems with names so the legend picks them up
        for comp_name in STACK_ORDER:
            color_hex = COMPONENT_COLORS.get(comp_name)
            if color_hex:
                dummy = self.plot_item.plot(
                    [], [], pen=pg.mkPen(color_hex, width=3), name=comp_name
                )
                self._curve_items.append(dummy)

    # -- Mouse Events / Tooltip -----------------------------------------------

    def _on_mouse_move(self, ev):
        """Update crosshair and tooltip on mouse move."""
        if self._contributions is None or self._n_months == 0:
            return

        mouse_pos = ev.pos()
        scene_pos = self.mapToScene(mouse_pos)
        vb_rect = self.view_box.sceneBoundingRect()

        if not vb_rect.contains(scene_pos):
            self._hide_interactive()
            return

        view_pos = self.view_box.mapSceneToView(scene_pos)
        idx = int(max(0, min(round(view_pos.x()), self._n_months - 1)))

        # Update vertical crosshair
        if self._show_crosshair:
            self._crosshair_v.setPos(view_pos.x())
            self._crosshair_v.setVisible(True)
        else:
            self._crosshair_v.setVisible(False)

        # Update tooltip
        if self._show_hover_tooltip:
            self._update_tooltip(idx, mouse_pos)
        else:
            self._tooltip.setVisible(False)

    def _on_mouse_leave(self, ev):
        """Hide interactive elements on mouse leave."""
        self._hide_interactive()

    def _hide_interactive(self):
        """Hide crosshair and tooltip."""
        if self._crosshair_v:
            self._crosshair_v.setVisible(False)
        self._tooltip.setVisible(False)

    def _update_tooltip(self, idx: int, mouse_pos):
        """Build and position the tooltip for the given month index."""
        if idx < 0 or idx >= len(self._contributions):
            self._tooltip.setVisible(False)
            return

        month_contribs = self._contributions[idx]
        month_label = self._month_labels[idx] if idx < len(self._month_labels) else "?"

        # Headline value
        headline_str = ""
        if self._headline_values is not None and idx < len(self._headline_values):
            hv = self._headline_values[idx]
            if not np.isnan(hv):
                headline_str = f"{hv:.1f}%"

        # Sort by absolute contribution (largest first)
        sorted_contribs = sorted(month_contribs, key=lambda x: abs(x[1]), reverse=True)

        # Build rich-text tooltip
        lines = [f"<b>{month_label}</b>"]
        if headline_str:
            lines[0] += f" &mdash; Headline: <b>{headline_str}</b>"

        for comp_name, contrib in sorted_contribs:
            color_hex = COMPONENT_COLORS.get(comp_name, "#888888")
            sign = "+" if contrib >= 0 else ""
            lines.append(
                f'<span style="color:{color_hex};">\u25a0</span> '
                f'{comp_name:<20s} {sign}{contrib:.2f}%'
            )

        self._tooltip.setText("<br>".join(lines))
        self._tooltip.adjustSize()

        # Position tooltip near cursor, offset to avoid overlap
        tip_w = self._tooltip.width()
        tip_h = self._tooltip.height()
        x = int(mouse_pos.x()) + 16
        y = int(mouse_pos.y()) - tip_h // 2

        # Keep within widget bounds
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

    # -- Theme ----------------------------------------------------------------

    def _apply_gridlines(self):
        """Override base to respect the show_gridlines setting."""
        if self.plot_item is None:
            return
        grid_color = self._get_contrasting_grid_color()
        self.plot_item.showGrid(
            x=False, y=self._show_gridlines, alpha=0.3
        )
        self.plot_item.getAxis('bottom').setPen(color=grid_color, width=1)
        if self.plot_item.getAxis('right'):
            self.plot_item.getAxis('right').setPen(color=grid_color, width=1)

    def set_theme(self, theme: str):
        """Apply theme and update all visual elements."""
        super().set_theme(theme)

        # Update headline overlay line color
        if self._headline_line is not None:
            accent = self._get_theme_accent_color()
            self._headline_line.setPen(pg.mkPen(color=accent, width=2.5))

        # Update tooltip style
        self._apply_tooltip_style()

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
