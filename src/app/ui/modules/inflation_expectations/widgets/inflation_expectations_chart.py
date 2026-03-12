"""Inflation Expectations Chart - 5Y Breakeven, 10Y Breakeven, Michigan 1Y."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.date_index_axis import DraggableIndexDateAxisItem
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem

if TYPE_CHECKING:
    import pandas as pd

# Fixed secondary colors (5Y breakeven uses theme accent)
_10Y_COLOR = "#EF5350"    # Red
_MICHIGAN_COLOR = "#FFA726"  # Amber

SERIES_ORDER = ["5Y Breakeven", "10Y Breakeven", "Michigan 1Y"]


class InflationExpectationsChart(BaseChart):
    """Multi-line chart: 5Y Breakeven, 10Y Breakeven, Michigan 1Y + 2% reference."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._series_values: Dict[str, np.ndarray] = {}
        self._date_labels: list = []
        self._line_items: Dict[str, object] = {}
        self._ref_line = None
        self._legend = None
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._show_reference_line = True

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
        self._legend = self.plot_item.addLegend(offset=(10, 10))

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
        self._placeholder = QLabel("Loading inflation expectations data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #888888; background: transparent;")
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        if self.plot_item:
            self.plot_item.clear()
            self._line_items = {}
            self._ref_line = None
            self._legend.clear()
            self._setup_crosshair()

    def update_data(self, exp_df: "Optional[pd.DataFrame]", settings: dict):
        import pandas as pd

        if exp_df is None or exp_df.empty:
            self.show_placeholder("No inflation expectations data available.")
            return

        primary_col = "5Y Breakeven"
        if primary_col not in exp_df.columns:
            self.show_placeholder("No 5Y Breakeven data available.")
            return

        self._placeholder.setVisible(False)
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._show_reference_line = settings.get("show_reference_line", True)

        primary_series = exp_df[primary_col].dropna()
        if primary_series.empty:
            self.show_placeholder("No 5Y Breakeven data available.")
            return

        self._dates = primary_series.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]

        self.plot_item.clear()
        self._line_items = {}
        self._ref_line = None
        self._legend.clear()
        self._setup_crosshair()

        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)

        x = np.arange(len(self._dates))
        accent = self._get_theme_accent_color()

        self._series_values = {}
        all_vals = []

        for name in SERIES_ORDER:
            if name not in exp_df.columns:
                continue
            aligned = exp_df[name].reindex(primary_series.index)
            vals = aligned.values.astype(float)
            self._series_values[name] = vals

            if name == "5Y Breakeven":
                color = accent
                style = Qt.SolidLine
                width = 2
            elif name == "10Y Breakeven":
                color = _10Y_COLOR
                style = Qt.SolidLine
                width = 2
            else:  # Michigan 1Y
                color = _MICHIGAN_COLOR
                style = Qt.DotLine
                width = 2

            line = self.plot_item.plot(
                x, vals,
                pen=pg.mkPen(color=color, width=width, style=style),
                name=name,
            )
            line.setClipToView(True)
            self._line_items[name] = line

            valid = vals[~np.isnan(vals)]
            if len(valid) > 0:
                all_vals.extend(valid.tolist())

        if self._show_reference_line:
            self._ref_line = pg.InfiniteLine(
                pos=2.0, angle=0, movable=False,
                pen=pg.mkPen(color=(255, 80, 80), width=1.5, style=Qt.DashLine),
                label="Fed Target: 2%",
                labelOpts={"color": (255, 80, 80), "position": 0.05, "fill": None},
            )
            self.plot_item.addItem(self._ref_line, ignoreBounds=True)

        if all_vals:
            y_min = min(all_vals)
            y_max = max(all_vals)
            y_range = y_max - y_min if y_max != y_min else 1.0
            pad = y_range * 0.08
            self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)
        self._legend.setVisible(self._show_legend)

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

    def _update_tooltip(self, idx: int, mouse_pos):
        if not self._show_hover_tooltip:
            self._tooltip.setVisible(False)
            return
        if self._dates is None or idx < 0 or idx >= len(self._dates):
            self._tooltip.setVisible(False)
            return

        date_str = self._date_labels[idx] if idx < len(self._date_labels) else "?"
        lines = [f"<b>{date_str}</b>"]

        accent = self._get_theme_accent_color()
        for name in SERIES_ORDER:
            vals = self._series_values.get(name)
            if vals is None or idx >= len(vals):
                continue
            v = vals[idx]
            if np.isnan(v):
                continue
            if name == "5Y Breakeven":
                color_str = f"rgb({accent[0]},{accent[1]},{accent[2]})"
            elif name == "10Y Breakeven":
                color_str = _10Y_COLOR
            else:
                color_str = _MICHIGAN_COLOR
            lines.append(
                f'<span style="color:{color_str};">\u25a0</span> {name}: {v:.2f}%'
            )

        self._tooltip.setText("<br>".join(lines))
        self._tooltip.adjustSize()

        tip_w = self._tooltip.width()
        tip_h = self._tooltip.height()
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
        accent = self._get_theme_accent_color()
        for name, line in self._line_items.items():
            if name == "5Y Breakeven":
                line.setPen(pg.mkPen(color=accent, width=2, style=Qt.SolidLine))
            elif name == "10Y Breakeven":
                line.setPen(pg.mkPen(color=_10Y_COLOR, width=2, style=Qt.SolidLine))
            else:
                line.setPen(pg.mkPen(color=_MICHIGAN_COLOR, width=2, style=Qt.DotLine))
        self._placeholder.setStyleSheet("font-size: 16px; color: #888888; background: transparent;")
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
