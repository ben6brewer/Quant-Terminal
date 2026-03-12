"""Housing Starts Chart — Dual-mode: Raw stacked area or YoY% line."""

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
from app.utils.recession_bands import add_recession_bands

if TYPE_CHECKING:
    import pandas as pd

# Component colors
_SF_COLOR = "#66BB6A"      # Green
_MULTI_COLOR = "#FFA726"   # Orange


class HousingStartsChart(BaseChart):
    """Housing starts chart — stacked area (Raw) or single YoY% line."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._date_labels: list = []
        self._area_items: list = []
        self._yoy_line = None
        self._ref_line = None
        self._legend = None
        self._recession_bands: list = []
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._view_mode = "Raw"
        # Tooltip data
        self._sf_values: Optional[np.ndarray] = None
        self._multi_values: Optional[np.ndarray] = None
        self._total_values: Optional[np.ndarray] = None
        self._yoy_values: Optional[np.ndarray] = None

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
        self._placeholder = QLabel("Loading housing starts data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #888888; background: transparent;")
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        self._clear_plot()

    def _clear_plot(self):
        if self.plot_item:
            for item in self._area_items:
                self.plot_item.removeItem(item)
            self._area_items.clear()
            self._yoy_line = None
            self._ref_line = None
            self._recession_bands = []
            if self._legend:
                self._legend.clear()
            self.plot_item.clear()
            self._setup_crosshair()

    # ── Public update entry point ─────────────────────────────────────────

    def update_data(
        self,
        starts_df: "Optional[pd.DataFrame]",
        usrec_df: "Optional[pd.DataFrame]",
        settings: dict,
    ):
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._view_mode = settings.get("view_mode", "Raw")

        if self._view_mode == "YoY %":
            self._render_yoy(starts_df, usrec_df, settings)
        else:
            self._render_stacked(starts_df, usrec_df, settings)

    # ── Raw: stacked area ─────────────────────────────────────────────────

    def _render_stacked(self, starts_df, usrec_df, settings):
        import pandas as pd

        if starts_df is None or starts_df.empty:
            self.show_placeholder("No housing starts data available.")
            return

        show_recession = settings.get("show_recession_bands", True)
        show_sf = settings.get("show_sf", True)
        show_multi = settings.get("show_multi", True)

        if not show_sf and not show_multi:
            self.show_placeholder("No series selected.")
            return

        # Use first available column as reference index
        ref_col = None
        for col in ["Single-Family", "5+ Units"]:
            if col in starts_df.columns:
                ref_col = col
                break
        if ref_col is None:
            self.show_placeholder("No housing starts data available.")
            return

        ref_series = starts_df[ref_col].dropna()
        if ref_series.empty:
            self.show_placeholder("No housing starts data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = ref_series.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]

        self._sf_values = (
            starts_df["Single-Family"].reindex(ref_series.index).values.astype(float)
            if "Single-Family" in starts_df.columns else None
        )
        self._multi_values = (
            starts_df["5+ Units"].reindex(ref_series.index).values.astype(float)
            if "5+ Units" in starts_df.columns else None
        )
        self._total_values = (
            starts_df["Total Starts"].reindex(ref_series.index).values.astype(float)
            if "Total Starts" in starts_df.columns else None
        )

        self._clear_plot()
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))

        # Recession bands
        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(dt_index, method="ffill").fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        # Stacked area: SF + 5+ Units
        stacks = []
        if show_sf and self._sf_values is not None:
            stacks.append(("Single-Family", self._sf_values, _SF_COLOR))
        if show_multi and self._multi_values is not None:
            stacks.append(("5+ Units", self._multi_values, _MULTI_COLOR))

        cumsum = np.zeros(len(x))
        for label, vals, color_hex in stacks:
            safe_vals = np.nan_to_num(vals, nan=0.0)
            color = QColor(color_hex)
            fill_brush = pg.mkBrush(color.red(), color.green(), color.blue(), 180)
            fill_pen = pg.mkPen(color.red(), color.green(), color.blue(), 220, width=1)
            top = cumsum + safe_vals
            lower_curve = self.plot_item.plot(x, cumsum, pen=pg.mkPen(None))
            upper_curve = self.plot_item.plot(x, top, pen=fill_pen, name=label)
            fill = pg.FillBetweenItem(lower_curve, upper_curve, brush=fill_brush)
            self.plot_item.addItem(fill)
            self._area_items.extend([lower_curve, upper_curve, fill])
            cumsum = top

        # Y range
        y_max = float(np.nanmax(cumsum)) if len(cumsum) > 0 else 1.0
        pad = y_max * 0.08
        self.plot_item.setYRange(-pad, y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)
        self._legend.setVisible(self._show_legend)

    # ── YoY %: single Total Starts line ───────────────────────────────────

    def _render_yoy(self, starts_df, usrec_df, settings):
        import pandas as pd

        if starts_df is None or starts_df.empty or "Total Starts" not in starts_df.columns:
            self.show_placeholder("No housing starts data available.")
            return

        show_recession = settings.get("show_recession_bands", True)

        yoy = starts_df["Total Starts"].pct_change(periods=12) * 100
        yoy = yoy.dropna()
        if yoy.empty:
            self.show_placeholder("Not enough data for YoY% calculation.")
            return

        self._placeholder.setVisible(False)
        self._dates = yoy.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]
        self._yoy_values = yoy.values.astype(float)

        self._clear_plot()
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))
        accent = self._get_theme_accent_color()

        # Recession bands
        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(dt_index, method="ffill").fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        # 0% reference line
        self._ref_line = pg.InfiniteLine(
            pos=0, angle=0,
            pen=pg.mkPen(color="#888888", width=1, style=Qt.DashLine)
        )
        self.plot_item.addItem(self._ref_line)

        self._yoy_line = self.plot_item.plot(
            x, self._yoy_values,
            pen=pg.mkPen(color=accent, width=2.5)
        )
        self._yoy_line.setClipToView(True)

        valid = self._yoy_values[~np.isnan(self._yoy_values)]
        if len(valid) > 0:
            y_min = float(np.nanmin(valid))
            y_max = float(np.nanmax(valid))
            y_range = y_max - y_min if y_max != y_min else 2.0
            pad = y_range * 0.1
            self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)
        self._legend.setVisible(False)

    # ── Mouse interaction ─────────────────────────────────────────────────

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

        if self._view_mode == "YoY %":
            accent = self._get_theme_accent_color()
            if self._yoy_values is not None and idx < len(self._yoy_values):
                val = self._yoy_values[idx]
                if not np.isnan(val):
                    lines.append(
                        f'<span style="color:rgb({accent[0]},{accent[1]},{accent[2]});">\u25a0</span>'
                        f" Total Starts YoY: {val:+.1f}%"
                    )
        else:
            for label, vals, color in [
                ("Single-Family", self._sf_values, _SF_COLOR),
                ("5+ Units", self._multi_values, _MULTI_COLOR),
            ]:
                if vals is not None and idx < len(vals):
                    val = vals[idx]
                    if not np.isnan(val):
                        lines.append(
                            f'<span style="color:{color};">\u25a0</span>'
                            f" {label}: {val:.0f}K"
                        )
            if self._total_values is not None and idx < len(self._total_values):
                total = self._total_values[idx]
                if not np.isnan(total):
                    lines.append(f"<b>Total: {total:.0f}K</b>")

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

    # ── Theme ─────────────────────────────────────────────────────────────

    def set_theme(self, theme: str):
        super().set_theme(theme)
        self._apply_tooltip_style()
        if self._yoy_line is not None:
            accent = self._get_theme_accent_color()
            self._yoy_line.setPen(pg.mkPen(color=accent, width=2.5))
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
