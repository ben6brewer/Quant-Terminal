"""Retail Sales Chart — Dual-mode: Raw two-line or YoY% line."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.date_index_axis import DraggableIndexDateAxisItem
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem
from app.utils.recession_bands import add_recession_bands

if TYPE_CHECKING:
    import pandas as pd

_REAL_COLOR = "#66BB6A"


class RetailSalesChart(BaseChart):
    """Retail sales chart — two-line (Raw) or YoY% line."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._date_labels: list = []
        self._series_values: Dict[str, np.ndarray] = {}
        self._line_items: Dict[str, object] = {}
        self._ref_line = None
        self._legend = None
        self._recession_bands: list = []
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._view_mode = "Raw"

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
            f"border-radius: 4px; padding: 8px 10px; font-size: 12px;"
            f'font-family: "Menlo", "Consolas", "Courier New";'
        )

    def _setup_placeholder(self):
        self._placeholder = QLabel("Loading retail sales data...", self)
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
            self._series_values = {}
            if self._legend:
                self._legend.clear()
            self._setup_crosshair()

    def _clear_plot(self):
        if self.plot_item:
            self._ref_line = None
            self._recession_bands = []
            self._line_items = {}
            self._series_values = {}
            if self._legend:
                self._legend.clear()
            self.plot_item.clear()
            self._setup_crosshair()

    def update_data(self, retail_df: "Optional[pd.DataFrame]",
                    usrec_df: "Optional[pd.DataFrame]", settings: dict):
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._view_mode = settings.get("view_mode", "Raw")

        if self._view_mode == "YoY %":
            self._render_yoy(retail_df, usrec_df, settings)
        else:
            self._render_raw(retail_df, usrec_df, settings)

    def _render_raw(self, retail_df, usrec_df, settings):
        import pandas as pd

        if retail_df is None or retail_df.empty:
            self.show_placeholder("No retail sales data available.")
            return

        show_recession = settings.get("show_recession_bands", True)

        ref_col = "Retail Sales" if "Retail Sales" in retail_df.columns else None
        if ref_col is None:
            for col in retail_df.columns:
                ref_col = col
                break
        if ref_col is None:
            self.show_placeholder("No retail sales data available.")
            return

        ref_series = retail_df[ref_col].dropna()
        if ref_series.empty:
            self.show_placeholder("No retail sales data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = ref_series.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]

        self._clear_plot()
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))
        accent = self._get_theme_accent_color()

        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(dt_index, method="ffill").fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        series_config = [
            ("Retail Sales", accent, 2.5, Qt.SolidLine),
            ("Real Retail Sales", _REAL_COLOR, 2, Qt.SolidLine),
        ]
        all_vals = []
        for name, color, width, style in series_config:
            if name not in retail_df.columns:
                continue
            vals = retail_df[name].reindex(ref_series.index).values.astype(float)
            self._series_values[name] = vals
            pen = pg.mkPen(color=color, width=width, style=style)
            line = self.plot_item.plot(x, vals, pen=pen, name=name)
            line.setClipToView(True)
            self._line_items[name] = line
            valid = vals[~np.isnan(vals)]
            if len(valid) > 0:
                all_vals.extend(valid.tolist())

        if all_vals:
            y_min, y_max = min(all_vals), max(all_vals)
            pad = (y_max - y_min) * 0.08 if y_max != y_min else 1.0
            self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)
        self._legend.setVisible(self._show_legend)

    def _render_yoy(self, retail_df, usrec_df, settings):
        import pandas as pd

        if retail_df is None or retail_df.empty or "Retail Sales" not in retail_df.columns:
            self.show_placeholder("No retail sales data available.")
            return

        show_recession = settings.get("show_recession_bands", True)

        yoy = retail_df["Retail Sales"].pct_change(periods=12) * 100
        yoy = yoy.dropna()
        if yoy.empty:
            self.show_placeholder("Not enough data for YoY% calculation.")
            return

        self._placeholder.setVisible(False)
        self._dates = yoy.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]
        yoy_vals = yoy.values.astype(float)
        self._series_values = {"YoY %": yoy_vals}

        self._clear_plot()
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))
        accent = self._get_theme_accent_color()

        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(dt_index, method="ffill").fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        self._ref_line = pg.InfiniteLine(
            pos=0, angle=0, pen=pg.mkPen(color="#888888", width=1, style=Qt.DashLine)
        )
        self.plot_item.addItem(self._ref_line)

        line = self.plot_item.plot(x, yoy_vals, pen=pg.mkPen(color=accent, width=2.5))
        line.setClipToView(True)
        self._line_items["YoY %"] = line

        valid = yoy_vals[~np.isnan(yoy_vals)]
        if len(valid) > 0:
            y_min, y_max = float(np.nanmin(valid)), float(np.nanmax(valid))
            y_range = y_max - y_min if y_max != y_min else 2.0
            pad = y_range * 0.1
            self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)
        self._legend.setVisible(False)

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

        for name in self._series_values:
            vals = self._series_values[name]
            if idx >= len(vals):
                continue
            v = vals[idx]
            if np.isnan(v):
                continue
            if name == "Retail Sales" or name == "YoY %":
                color_str = f"rgb({accent[0]},{accent[1]},{accent[2]})"
            else:
                color_str = _REAL_COLOR
            if self._view_mode == "YoY %":
                lines.append(f'<span style="color:{color_str};">\u25a0</span> YoY: {v:+.1f}%')
            else:
                lines.append(f'<span style="color:{color_str};">\u25a0</span> {name}: ${v:,.0f}M')

        self._tooltip.setText("<br>".join(lines))
        self._tooltip.adjustSize()
        tip_w, tip_h = self._tooltip.width(), self._tooltip.height()
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
            if name in ("Retail Sales", "YoY %"):
                line.setPen(pg.mkPen(color=accent, width=2.5))
            else:
                line.setPen(pg.mkPen(color=_REAL_COLOR, width=2))
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
