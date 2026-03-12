"""Vehicle Sales Chart — Dual-mode: Raw multi-line or YoY% multi-line."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

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

_LIGHT_COLOR = "#66BB6A"   # Green
_HEAVY_COLOR = "#FF7043"   # Orange


class VehicleSalesChart(BaseChart):
    """Vehicle sales chart — multi-line in both Raw and YoY% modes."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._date_labels: list = []
        self._line_items: dict = {}
        self._ref_line = None
        self._legend = None
        self._recession_bands: list = []
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._view_mode = "Raw"
        # Tooltip data — Raw (M for Total/Light, K for Heavy)
        self._total_values: Optional[np.ndarray] = None
        self._light_values: Optional[np.ndarray] = None
        self._heavy_values: Optional[np.ndarray] = None
        # Tooltip data — YoY% (per-series)
        self._yoy_total_values: Optional[np.ndarray] = None
        self._yoy_light_values: Optional[np.ndarray] = None
        self._yoy_heavy_values: Optional[np.ndarray] = None

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
        self._placeholder = QLabel("Loading vehicle sales data...", self)
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
            self._line_items.clear()
            self._ref_line = None
            self._recession_bands = []
            if self._legend:
                self._legend.clear()
            self.plot_item.clear()
            self._setup_crosshair()

    # ── Public update entry point ─────────────────────────────────────────

    def update_data(
        self,
        vehicles_df: "Optional[pd.DataFrame]",
        usrec_df: "Optional[pd.DataFrame]",
        settings: dict,
    ):
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._view_mode = settings.get("view_mode", "Raw")

        if self._view_mode == "YoY %":
            self._render_yoy(vehicles_df, usrec_df, settings)
        else:
            self._render_raw(vehicles_df, usrec_df, settings)

    # ── Raw: multi-line ───────────────────────────────────────────────────

    def _render_raw(self, vehicles_df, usrec_df, settings):
        import pandas as pd

        if vehicles_df is None or vehicles_df.empty:
            self.show_placeholder("No vehicle sales data available.")
            return

        show_recession = settings.get("show_recession_bands", True)
        show_total = settings.get("show_total", True)
        show_light = settings.get("show_light_autos", True)
        show_heavy = settings.get("show_heavy_trucks", True)

        if not show_total and not show_light and not show_heavy:
            self.show_placeholder("No series selected.")
            return

        # Use Total as reference index, fallback to first available
        ref_col = None
        for col in ["Total Vehicle Sales", "Light Autos", "Heavy Trucks"]:
            if col in vehicles_df.columns:
                ref_col = col
                break
        if ref_col is None:
            self.show_placeholder("No vehicle sales data available.")
            return

        ref_series = vehicles_df[ref_col].dropna()
        if ref_series.empty:
            self.show_placeholder("No vehicle sales data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = ref_series.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]

        # Store raw values for tooltip (original FRED units)
        self._total_values = (
            vehicles_df["Total Vehicle Sales"].reindex(ref_series.index).values.astype(float)
            if "Total Vehicle Sales" in vehicles_df.columns else None
        )
        self._light_values = (
            vehicles_df["Light Autos"].reindex(ref_series.index).values.astype(float)
            if "Light Autos" in vehicles_df.columns else None
        )
        # Heavy Trucks raw values are in thousands
        self._heavy_values = (
            vehicles_df["Heavy Trucks"].reindex(ref_series.index).values.astype(float)
            if "Heavy Trucks" in vehicles_df.columns else None
        )

        self._clear_plot()
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))
        accent = self._get_theme_accent_color()

        # Recession bands
        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(dt_index, method="ffill").fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        # Build series list: (name, plot_values, color, width, style)
        # Total & Light Autos are in millions; Heavy Trucks converted K→M for same Y-axis
        series_to_plot = []
        if show_total and self._total_values is not None:
            series_to_plot.append(("Total", self._total_values, accent, 2.5, Qt.SolidLine))
        if show_light and self._light_values is not None:
            series_to_plot.append(("Light Autos", self._light_values, _LIGHT_COLOR, 2, Qt.SolidLine))
        if show_heavy and self._heavy_values is not None:
            # Convert thousands → millions so it shares the Y-axis scale
            series_to_plot.append(("Heavy Trucks", self._heavy_values / 1000, _HEAVY_COLOR, 2, Qt.DashLine))

        all_vals = []
        for name, vals, color, width, style in series_to_plot:
            line = self.plot_item.plot(
                x, vals,
                pen=pg.mkPen(color=color, width=width, style=style),
                name=name,
            )
            line.setClipToView(True)
            self._line_items[name] = line
            all_vals.append(vals)

        # Y range
        if all_vals:
            combined = np.concatenate(all_vals)
            valid = combined[~np.isnan(combined)]
            if len(valid) > 0:
                y_min = float(np.nanmin(valid))
                y_max = float(np.nanmax(valid))
                y_range = y_max - y_min if y_max != y_min else 1.0
                pad = y_range * 0.08
                self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)
        self._legend.setVisible(self._show_legend)

    # ── YoY %: multi-line (Total / Light Autos / Heavy Trucks) ──────────

    def _render_yoy(self, vehicles_df, usrec_df, settings):
        import pandas as pd

        show_total = settings.get("show_total", True)
        show_light = settings.get("show_light_autos", True)
        show_heavy = settings.get("show_heavy_trucks", True)

        if not show_total and not show_light and not show_heavy:
            self.show_placeholder("No series selected.")
            return

        if vehicles_df is None or vehicles_df.empty:
            self.show_placeholder("No vehicle sales data available.")
            return

        show_recession = settings.get("show_recession_bands", True)

        # Compute YoY% for each series
        yoy_series = {}
        for col, key, show in [
            ("Total Vehicle Sales", "total", show_total),
            ("Light Autos", "light", show_light),
            ("Heavy Trucks", "heavy", show_heavy),
        ]:
            if show and col in vehicles_df.columns:
                s = vehicles_df[col].pct_change(periods=12) * 100
                s = s.dropna()
                if not s.empty:
                    yoy_series[key] = s

        if not yoy_series:
            self.show_placeholder("Not enough data for YoY% calculation.")
            return

        # Use union of all indices so all series align
        combined_idx = yoy_series[next(iter(yoy_series))].index
        for s in yoy_series.values():
            combined_idx = combined_idx.union(s.index)
        combined_idx = combined_idx.sort_values()

        self._placeholder.setVisible(False)
        self._dates = combined_idx.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]

        # Store per-series YoY values for tooltip
        self._yoy_total_values = (
            yoy_series["total"].reindex(combined_idx).values.astype(float)
            if "total" in yoy_series else None
        )
        self._yoy_light_values = (
            yoy_series["light"].reindex(combined_idx).values.astype(float)
            if "light" in yoy_series else None
        )
        self._yoy_heavy_values = (
            yoy_series["heavy"].reindex(combined_idx).values.astype(float)
            if "heavy" in yoy_series else None
        )

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

        # Plot each YoY% line
        series_to_plot = []
        if self._yoy_total_values is not None:
            series_to_plot.append(("Total YoY", self._yoy_total_values, accent, 2.5, Qt.SolidLine))
        if self._yoy_light_values is not None:
            series_to_plot.append(("Light Autos YoY", self._yoy_light_values, _LIGHT_COLOR, 2, Qt.SolidLine))
        if self._yoy_heavy_values is not None:
            series_to_plot.append(("Heavy Trucks YoY", self._yoy_heavy_values, _HEAVY_COLOR, 2, Qt.DashLine))

        all_vals = []
        for name, vals, color, width, style in series_to_plot:
            line = self.plot_item.plot(
                x, vals,
                pen=pg.mkPen(color=color, width=width, style=style),
                name=name,
            )
            line.setClipToView(True)
            self._line_items[name] = line
            all_vals.append(vals)

        if all_vals:
            combined = np.concatenate(all_vals)
            valid = combined[~np.isnan(combined)]
            if len(valid) > 0:
                y_min = float(np.nanmin(valid))
                y_max = float(np.nanmax(valid))
                y_range = y_max - y_min if y_max != y_min else 2.0
                pad = y_range * 0.1
                self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)
        self._legend.setVisible(self._show_legend)

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
            for label, vals, color in [
                ("Total YoY", self._yoy_total_values, f"rgb({accent[0]},{accent[1]},{accent[2]})"),
                ("Light Autos YoY", self._yoy_light_values, _LIGHT_COLOR),
                ("Heavy Trucks YoY", self._yoy_heavy_values, _HEAVY_COLOR),
            ]:
                if vals is not None and idx < len(vals):
                    val = vals[idx]
                    if not np.isnan(val):
                        lines.append(
                            f'<span style="color:{color};">\u25a0</span>'
                            f" {label}: {val:+.1f}%"
                        )
        else:
            accent = self._get_theme_accent_color()
            # Total & Light Autos in millions, Heavy Trucks in thousands
            for label, vals, color, unit in [
                ("Total", self._total_values, f"rgb({accent[0]},{accent[1]},{accent[2]})", "M SAAR"),
                ("Light Autos", self._light_values, _LIGHT_COLOR, "M SAAR"),
                ("Heavy Trucks", self._heavy_values, _HEAVY_COLOR, "K SAAR"),
            ]:
                if vals is not None and idx < len(vals):
                    val = vals[idx]
                    if not np.isnan(val):
                        lines.append(
                            f'<span style="color:{color};">\u25a0</span>'
                            f" {label}: {val:.1f}{unit}"
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

    # ── Theme ─────────────────────────────────────────────────────────────

    def set_theme(self, theme: str):
        super().set_theme(theme)
        self._apply_tooltip_style()
        accent = self._get_theme_accent_color()
        # Update accent-colored lines in both Raw and YoY% modes
        if "Total" in self._line_items:
            self._line_items["Total"].setPen(pg.mkPen(color=accent, width=2.5))
        if "Total YoY" in self._line_items:
            self._line_items["Total YoY"].setPen(pg.mkPen(color=accent, width=2.5))
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
