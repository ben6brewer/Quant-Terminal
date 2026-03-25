"""Factor Attribution Chart — stacked area (cumulative) and stacked bar (periodic)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes import (
    DraggablePercentageAxisItem,
    DraggableAxisItem,
)

if TYPE_CHECKING:
    from ..services.factor_regression_service import FactorRegressionResult

# ── Color palette ───────────────────────────────────────────────────────────

FACTOR_COLORS: dict[str, str] = {
    # Fama-French
    "Mkt-RF": "#4FC3F7",  # Blue
    "SMB": "#66BB6A",  # Green
    "HML": "#EF5350",  # Red
    "RMW": "#26C6DA",  # Teal
    "CMA": "#FFA726",  # Orange
    "UMD": "#AB47BC",  # Purple
    # Q-Factor
    "R_MKT": "#4FC3F7",
    "R_ME": "#66BB6A",
    "R_IA": "#FFA726",
    "R_ROE": "#26C6DA",
    "R_EG": "#EC407A",
    # AQR
    "BAB": "#FF7043",  # Deep orange
    "QMJ": "#7E57C2",  # Deep purple
    "HML_DEVIL": "#D4E157",  # Lime
    # Attribution
    "Alpha": "#FFD54F",  # Gold
    "Residual": "#9E9E9E",  # Gray
}


def _color_tuple(hex_color: str, alpha: int = 200) -> tuple:
    c = QColor(hex_color)
    return (c.red(), c.green(), c.blue(), alpha)


class _DateIndexAxis(pg.AxisItem):
    """Maps integer indices to date label strings."""

    def __init__(self, orientation="bottom"):
        super().__init__(orientation)
        self._labels: list[str] = []

    def set_labels(self, labels: list[str]):
        self._labels = labels

    def tickStrings(self, values, scale, spacing):
        out = []
        for v in values:
            idx = int(round(v))
            if 0 <= idx < len(self._labels):
                out.append(self._labels[idx])
            else:
                out.append("")
        return out


class FactorAttributionChart(BaseChart):
    """Stacked area (cumulative) and stacked bar (periodic) attribution chart."""

    def __init__(self, parent=None):
        self._placeholder: Optional[QLabel] = None
        super().__init__(parent=parent)

        self._result: Optional["FactorRegressionResult"] = None
        self._view_mode = "cumulative"
        self._show_gridlines = True
        self._plot_items: list = []
        self._legend = None
        self._legend_dummies: list = []
        self._date_labels: list[str] = []

        self._setup_plots()
        self._setup_crosshair()
        self._setup_tooltip()
        self._setup_placeholder()

    def _setup_plots(self):
        self._bottom_axis = _DateIndexAxis(orientation="bottom")
        self._right_axis = DraggablePercentageAxisItem(orientation="right")
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
        self.plot_item.showGrid(x=False, y=True, alpha=0.3)

    def _setup_crosshair(self):
        color = self._get_crosshair_color()
        pen = pg.mkPen(color=color, width=1, style=Qt.DashLine)
        self._crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._crosshair_v.setVisible(False)
        self.plot_item.addItem(self._crosshair_v, ignoreBounds=True)
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
            f"border-radius: 4px;"
            f"padding: 8px 10px;"
            f"font-size: 12px;"
            f'font-family: "Menlo", "Consolas", "Courier New";'
        )

    def _setup_placeholder(self):
        self._placeholder = QLabel("Click Run to compute factor attribution", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        self._clear_items()

    def _clear_items(self):
        for item in self._plot_items:
            self.plot_item.removeItem(item)
        self._plot_items.clear()

        for item in self._legend_dummies:
            self.plot_item.removeItem(item)
        self._legend_dummies.clear()

        if self._legend is not None:
            self._legend.clear()
            try:
                self._legend.scene().removeItem(self._legend)
            except Exception:
                pass
            self.plot_item.legend = None
            self._legend = None

        self._date_labels.clear()

    # ── Public API ──────────────────────────────────────────────────────────

    def update_data(self, result: "FactorRegressionResult", view_mode: str):
        """Render the chart from a regression result."""
        self.setUpdatesEnabled(False)
        try:
            self._result = result
            self._view_mode = view_mode
            self._render()
        finally:
            self.setUpdatesEnabled(True)

    def set_view_mode(self, view_mode: str):
        """Re-render with a different view mode without new data."""
        if self._result is None:
            return
        self._view_mode = view_mode
        self.setUpdatesEnabled(False)
        try:
            self._render()
        finally:
            self.setUpdatesEnabled(True)

    def apply_settings(self, settings: dict):
        self._show_gridlines = settings.get("show_gridlines", True)

    def _render(self):
        self._clear_items()
        if self._result is None:
            return

        self._placeholder.setVisible(False)

        # Build date labels
        import pandas as pd

        dates = pd.DatetimeIndex(self._result.dates)
        freq = self._result.frequency
        if freq == "monthly":
            self._date_labels = [d.strftime("%b '%y") for d in dates]
        elif freq == "weekly":
            self._date_labels = [d.strftime("%m/%d/%y") for d in dates]
        else:
            self._date_labels = [d.strftime("%Y-%m-%d") for d in dates]
        self._bottom_axis.set_labels(self._date_labels)

        if self._view_mode == "cumulative":
            self._render_cumulative()
        else:
            self._render_periodic()

        self._add_legend()
        self.plot_item.showGrid(x=False, y=self._show_gridlines, alpha=0.3)
        self.plot_item.autoRange()

    # ── Cumulative stacked area ─────────────────────────────────────────────

    def _render_cumulative(self):
        result = self._result
        n = len(result.dates)
        x = np.arange(n, dtype=float)

        # Order: factors, alpha, residual
        components = list(result.factor_names) + ["Alpha", "Residual"]
        series: dict[str, np.ndarray] = {}
        for f in result.factor_names:
            series[f] = np.cumsum(result.factor_contributions[f]) * 100
        series["Alpha"] = np.cumsum(result.alpha_series) * 100
        series["Residual"] = np.cumsum(result.residuals) * 100

        # Stack positive and negative series separately
        # Simple approach: cumulative stack in order
        cumulative_bottom = np.zeros(n)

        for comp in components:
            vals = series[comp]
            color_hex = FACTOR_COLORS.get(comp, "#888888")
            top = cumulative_bottom + vals

            # Use FillBetweenItem for area
            pen_color = _color_tuple(color_hex, 255)
            brush_color = _color_tuple(color_hex, 120)

            curve_bottom = pg.PlotDataItem(x, cumulative_bottom, pen=pg.mkPen(None))
            curve_top = pg.PlotDataItem(x, top, pen=pg.mkPen(color=pen_color, width=1))

            fill = pg.FillBetweenItem(curve_bottom, curve_top, brush=pg.mkBrush(*brush_color))
            self.plot_item.addItem(curve_bottom)
            self.plot_item.addItem(curve_top)
            self.plot_item.addItem(fill)
            self._plot_items.extend([curve_bottom, curve_top, fill])

            cumulative_bottom = top

        # Bold total excess return line
        total_cum = np.cumsum(result.asset_excess_returns) * 100
        accent = self._get_theme_accent_color()
        total_line = self.plot_item.plot(
            x, total_cum,
            pen=pg.mkPen(color=accent, width=2.5),
        )
        self._plot_items.append(total_line)

        # Zero reference line
        zero_line = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(color=(128, 128, 128), width=1, style=Qt.DashLine))
        self.plot_item.addItem(zero_line, ignoreBounds=True)
        self._plot_items.append(zero_line)

    # ── Periodic stacked bar ────────────────────────────────────────────────

    def _render_periodic(self):
        result = self._result
        n = len(result.dates)
        x = np.arange(n, dtype=float)
        BAR_WIDTH = 0.8

        components = list(result.factor_names) + ["Alpha", "Residual"]
        values: dict[str, np.ndarray] = {}
        for f in result.factor_names:
            values[f] = result.factor_contributions[f] * 100
        values["Alpha"] = result.alpha_series * 100
        values["Residual"] = result.residuals * 100

        pos_cumsum = np.zeros(n)
        neg_cumsum = np.zeros(n)

        for comp in components:
            vals = values[comp]
            color_hex = FACTOR_COLORS.get(comp, "#888888")
            c = QColor(color_hex)
            brush = pg.mkBrush(c.red(), c.green(), c.blue(), 200)

            pos_vals = np.where(vals > 0, vals, 0.0)
            neg_vals = np.where(vals < 0, vals, 0.0)

            if np.any(pos_vals != 0):
                bar = pg.BarGraphItem(
                    x=x, height=pos_vals, y0=pos_cumsum.copy(),
                    width=BAR_WIDTH, brush=brush, pen=pg.mkPen(None),
                )
                self.plot_item.addItem(bar)
                self._plot_items.append(bar)
                pos_cumsum += pos_vals

            if np.any(neg_vals != 0):
                bar = pg.BarGraphItem(
                    x=x, height=neg_vals, y0=neg_cumsum.copy(),
                    width=BAR_WIDTH, brush=brush, pen=pg.mkPen(None),
                )
                self.plot_item.addItem(bar)
                self._plot_items.append(bar)
                neg_cumsum += neg_vals

        # Zero reference line
        zero_line = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(color=(128, 128, 128), width=1, style=Qt.DashLine))
        self.plot_item.addItem(zero_line, ignoreBounds=True)
        self._plot_items.append(zero_line)

    # ── Legend ──────────────────────────────────────────────────────────────

    def _add_legend(self):
        if self._result is None:
            return
        self._legend = self.plot_item.addLegend(offset=(60, 10))
        self._legend.setBrush(pg.mkBrush(color=(0, 0, 0, 100)))

        components = list(self._result.factor_names) + ["Alpha", "Residual"]
        for comp in components:
            color_hex = FACTOR_COLORS.get(comp, "#888888")
            dummy = self.plot_item.plot(
                [], [], pen=pg.mkPen(color_hex, width=8), name=comp,
            )
            self._legend_dummies.append(dummy)

    # ── Mouse Events / Tooltip ──────────────────────────────────────────────

    def _on_mouse_move(self, ev):
        if self._result is None or len(self._result.dates) == 0:
            return

        mouse_pos = ev.pos()
        scene_pos = self.mapToScene(mouse_pos)
        vb_rect = self.view_box.sceneBoundingRect()

        if not vb_rect.contains(scene_pos):
            self._hide_interactive()
            return

        view_pos = self.view_box.mapSceneToView(scene_pos)
        n = len(self._result.dates)
        idx = int(max(0, min(round(view_pos.x()), n - 1)))

        self._crosshair_v.setPos(view_pos.x())
        self._crosshair_v.setVisible(True)

        self._update_tooltip(idx, mouse_pos)

    def _on_mouse_leave(self, ev):
        self._hide_interactive()

    def _hide_interactive(self):
        if self._crosshair_v:
            self._crosshair_v.setVisible(False)
        self._tooltip.setVisible(False)

    def _update_tooltip(self, idx: int, mouse_pos):
        result = self._result
        if result is None or idx >= len(result.dates):
            self._tooltip.setVisible(False)
            return

        date_label = self._date_labels[idx] if idx < len(self._date_labels) else "?"

        lines = [f"<b>{date_label}</b>"]

        # Show each factor contribution
        total = 0.0
        for f in result.factor_names:
            contrib = result.factor_contributions[f][idx]
            total += contrib
            color_hex = FACTOR_COLORS.get(f, "#888888")
            sign = "+" if contrib >= 0 else ""
            lines.append(
                f'<span style="color:{color_hex};">\u25a0</span> '
                f'{f:<12s} {sign}{contrib * 100:.3f}%'
            )

        # Alpha
        alpha_val = result.alpha_series[idx]
        total += alpha_val
        lines.append(
            f'<span style="color:{FACTOR_COLORS["Alpha"]};">\u25a0</span> '
            f'{"Alpha":<12s} {("+" if alpha_val >= 0 else "")}{alpha_val * 100:.3f}%'
        )

        # Residual
        resid = result.residuals[idx]
        total += resid
        lines.append(
            f'<span style="color:{FACTOR_COLORS["Residual"]};">\u25a0</span> '
            f'{"Residual":<12s} {("+" if resid >= 0 else "")}{resid * 100:.3f}%'
        )

        # Total
        excess = result.asset_excess_returns[idx]
        lines.append(f"<br><b>Total Excess: {excess * 100:+.3f}%</b>")

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

    # ── Theme ───────────────────────────────────────────────────────────────

    def _apply_gridlines(self):
        if self.plot_item is None:
            return
        grid_color = self._get_contrasting_grid_color()
        self.plot_item.showGrid(x=False, y=self._show_gridlines, alpha=0.3)
        self.plot_item.getAxis("bottom").setPen(color=grid_color, width=1)
        if self.plot_item.getAxis("right"):
            self.plot_item.getAxis("right").setPen(color=grid_color, width=1)

    def set_theme(self, theme: str):
        super().set_theme(theme)
        self._apply_tooltip_style()
        if self._placeholder:
            self._placeholder.setStyleSheet(
                "font-size: 16px; color: #888888; background: transparent;"
            )
        text_color = self._get_label_text_color()
        for axis_name in ("bottom", "right"):
            axis = self.plot_item.getAxis(axis_name)
            if axis:
                axis.setTextPen(text_color)

    def showEvent(self, event):
        super().showEvent(event)
        if self._placeholder and self._placeholder.isVisible():
            self._placeholder.setGeometry(self.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._placeholder and self._placeholder.isVisible():
            self._placeholder.setGeometry(self.rect())
