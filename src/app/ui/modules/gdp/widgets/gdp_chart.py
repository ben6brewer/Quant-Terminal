"""GDP Chart — Dual-mode: Raw stacked components or YoY% growth line, with Real/Nominal toggle."""

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
_PCE_COLOR = "#4FC3F7"        # Light blue
_INVESTMENT_COLOR = "#66BB6A"  # Green
_GOVERNMENT_COLOR = "#FFA726"  # Orange
_EXPORTS_COLOR = "#AB47BC"    # Purple
_IMPORTS_COLOR = "#EF5350"    # Red


class GdpChart(BaseChart):
    """GDP chart — stacked area (Raw) or single growth line (YoY %)."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._date_labels: list = []
        self._area_items: list = []
        self._growth_line = None
        self._ref_line = None
        self._legend = None
        self._recession_bands: list = []
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._view_mode = "Raw"
        self._data_mode = "Real"
        # Tooltip data
        self._pce_values: Optional[np.ndarray] = None
        self._inv_values: Optional[np.ndarray] = None
        self._gov_values: Optional[np.ndarray] = None
        self._exp_values: Optional[np.ndarray] = None
        self._imp_values: Optional[np.ndarray] = None
        self._real_gdp_values: Optional[np.ndarray] = None
        self._nominal_gdp_values: Optional[np.ndarray] = None
        self._growth_values: Optional[np.ndarray] = None

        self._setup_plots()
        self._setup_crosshair()
        self._setup_tooltip()
        self._setup_placeholder()

    def _setup_plots(self):
        self._bottom_axis = DraggableIndexDateAxisItem(orientation="bottom")
        self._right_axis = DraggableAxisItem(orientation="right")
        self._right_axis.setWidth(70)

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
        self._placeholder = QLabel("Loading GDP data...", self)
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
            self._growth_line = None
            self._ref_line = None
            self._recession_bands = []
            if self._legend:
                self._legend.clear()
            self.plot_item.clear()
            self._setup_crosshair()

    # ── Public update entry point ─────────────────────────────────────────

    def update_data(
        self,
        comp_df: "Optional[pd.DataFrame]",
        nom_comp_df: "Optional[pd.DataFrame]",
        growth_df: "Optional[pd.DataFrame]",
        gdp_df: "Optional[pd.DataFrame]",
        usrec_df: "Optional[pd.DataFrame]",
        settings: dict,
    ):
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._view_mode = settings.get("view_mode", "Raw")
        self._data_mode = settings.get("data_mode", "Real")

        # Store GDP totals for tooltip
        if gdp_df is not None and not gdp_df.empty:
            if "Real GDP" in gdp_df.columns:
                self._real_gdp_values = gdp_df["Real GDP"].values.astype(float)
            if "Nominal GDP" in gdp_df.columns:
                self._nominal_gdp_values = gdp_df["Nominal GDP"].values.astype(float)
            self._gdp_dates = gdp_df.index.values
        else:
            self._real_gdp_values = None
            self._nominal_gdp_values = None
            self._gdp_dates = None

        if self._view_mode == "YoY %":
            self._render_growth(growth_df, gdp_df, usrec_df, settings)
        else:
            active_comp = nom_comp_df if self._data_mode == "Nominal" else comp_df
            self._render_components(active_comp, usrec_df, settings)

    # ── Raw: stacked area ─────────────────────────────────────────────────

    def _render_components(self, comp_df, usrec_df, settings):
        import pandas as pd

        if comp_df is None or comp_df.empty:
            self.show_placeholder("No GDP components data available.")
            return

        show_recession = settings.get("show_recession_bands", True)
        show_pce = settings.get("show_pce", True)
        show_investment = settings.get("show_investment", True)
        show_government = settings.get("show_government", True)
        show_exports = settings.get("show_exports", True)
        show_imports = settings.get("show_imports", True)

        # Find reference column
        ref_col = None
        for col in ["PCE", "Investment", "Government"]:
            if col in comp_df.columns:
                ref_col = col
                break
        if ref_col is None:
            self.show_placeholder("No GDP components data available.")
            return

        ref_series = comp_df[ref_col].dropna()
        if ref_series.empty:
            self.show_placeholder("No GDP components data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = ref_series.index.values
        self._date_labels = [
            f"Q{(pd.Timestamp(d).month - 1) // 3 + 1} {pd.Timestamp(d).year}"
            for d in self._dates
        ]

        self._pce_values = comp_df["PCE"].reindex(ref_series.index).values.astype(float) if "PCE" in comp_df.columns else None
        self._inv_values = comp_df["Investment"].reindex(ref_series.index).values.astype(float) if "Investment" in comp_df.columns else None
        self._gov_values = comp_df["Government"].reindex(ref_series.index).values.astype(float) if "Government" in comp_df.columns else None
        self._exp_values = comp_df["Exports"].reindex(ref_series.index).values.astype(float) if "Exports" in comp_df.columns else None
        self._imp_values = comp_df["Imports"].reindex(ref_series.index).values.astype(float) if "Imports" in comp_df.columns else None

        self._clear_plot()
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))

        # Recession bands
        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(dt_index, method="ffill").fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        # Stacked area upward: PCE, Investment, Government, Exports
        stacks = []
        if show_pce and self._pce_values is not None:
            stacks.append(("PCE", self._pce_values, _PCE_COLOR))
        if show_investment and self._inv_values is not None:
            stacks.append(("Investment", self._inv_values, _INVESTMENT_COLOR))
        if show_government and self._gov_values is not None:
            stacks.append(("Government", self._gov_values, _GOVERNMENT_COLOR))
        if show_exports and self._exp_values is not None:
            stacks.append(("Exports", self._exp_values, _EXPORTS_COLOR))

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

        # Imports below zero as filled area
        if show_imports and self._imp_values is not None:
            neg_imports = -np.nan_to_num(self._imp_values, nan=0.0)
            color = QColor(_IMPORTS_COLOR)
            fill_brush = pg.mkBrush(color.red(), color.green(), color.blue(), 180)
            fill_pen = pg.mkPen(color.red(), color.green(), color.blue(), 220, width=1)
            zero_curve = self.plot_item.plot(x, np.zeros(len(x)), pen=pg.mkPen(None))
            imp_curve = self.plot_item.plot(x, neg_imports, pen=fill_pen, name="Imports")
            fill = pg.FillBetweenItem(zero_curve, imp_curve, brush=fill_brush)
            self.plot_item.addItem(fill)
            self._area_items.extend([zero_curve, imp_curve, fill])

        # Y range
        y_max = float(np.nanmax(cumsum)) if len(cumsum) > 0 else 1.0
        y_min = 0.0
        if show_imports and self._imp_values is not None:
            imp_max = float(np.nanmax(np.nan_to_num(self._imp_values, nan=0.0)))
            y_min = -imp_max
        pad = (y_max - y_min) * 0.08
        self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)
        self._legend.setVisible(self._show_legend)

    # ── YoY %: single growth line ────────────────────────────────────────

    def _render_growth(self, growth_df, gdp_df, usrec_df, settings):
        import pandas as pd

        show_recession = settings.get("show_recession_bands", True)

        if self._data_mode == "Nominal" and gdp_df is not None and "Nominal GDP" in gdp_df.columns:
            # Compute nominal YoY% from Nominal GDP (quarterly → periods=4)
            nominal_yoy = gdp_df["Nominal GDP"].pct_change(periods=4) * 100
            nominal_yoy = nominal_yoy.dropna()
            if nominal_yoy.empty:
                self.show_placeholder("Not enough data for Nominal GDP YoY%.")
                return
            series = nominal_yoy
            growth_label = "Nominal GDP YoY"
        else:
            # Real mode: use pre-computed GDP Growth (QoQ annualized)
            if growth_df is None or growth_df.empty:
                self.show_placeholder("No GDP growth data available.")
                return
            col = "GDP Growth" if "GDP Growth" in growth_df.columns else growth_df.columns[0]
            series = growth_df[col].dropna()
            growth_label = "GDP Growth"

        if series.empty:
            self.show_placeholder("No GDP growth data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = series.index.values
        self._date_labels = [
            f"Q{(pd.Timestamp(d).month - 1) // 3 + 1} {pd.Timestamp(d).year}"
            for d in self._dates
        ]
        self._growth_values = series.values.astype(float)
        self._growth_label = growth_label

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

        self._growth_line = self.plot_item.plot(
            x, self._growth_values,
            pen=pg.mkPen(color=accent, width=2.5)
        )
        self._growth_line.setClipToView(True)

        valid = self._growth_values[~np.isnan(self._growth_values)]
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
            label = getattr(self, "_growth_label", "GDP Growth")
            if self._growth_values is not None and idx < len(self._growth_values):
                val = self._growth_values[idx]
                if not np.isnan(val):
                    lines.append(
                        f'<span style="color:rgb({accent[0]},{accent[1]},{accent[2]});">\u25a0</span>'
                        f" {label}: {val:+.1f}%"
                    )
        else:
            for label, vals, color in [
                ("PCE", self._pce_values, _PCE_COLOR),
                ("Investment", self._inv_values, _INVESTMENT_COLOR),
                ("Government", self._gov_values, _GOVERNMENT_COLOR),
                ("Exports", self._exp_values, _EXPORTS_COLOR),
                ("Imports", self._imp_values, _IMPORTS_COLOR),
            ]:
                if vals is not None and idx < len(vals):
                    val = vals[idx]
                    if not np.isnan(val):
                        lines.append(
                            f'<span style="color:{color};">\u25a0</span>'
                            f" {label}: ${val:.2f}T"
                        )
            # Bold total from GDP data
            gdp_vals = self._nominal_gdp_values if self._data_mode == "Nominal" else self._real_gdp_values
            gdp_label = "Nominal GDP" if self._data_mode == "Nominal" else "Real GDP"
            if gdp_vals is not None and self._gdp_dates is not None:
                import pandas as pd
                current_date = self._dates[idx]
                gdp_idx = np.searchsorted(self._gdp_dates, current_date)
                if gdp_idx < len(gdp_vals):
                    total = gdp_vals[gdp_idx]
                    if not np.isnan(total):
                        lines.append(f"<b>{gdp_label}: ${total:.2f}T</b>")

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
        if self._growth_line is not None:
            accent = self._get_theme_accent_color()
            self._growth_line.setPen(pg.mkPen(color=accent, width=2.5))
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
