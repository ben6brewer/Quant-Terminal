"""Payrolls Chart - Stacked bar chart of sector MoM payroll changes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem
from app.ui.modules.labor_market.utils import add_recession_bands

if TYPE_CHECKING:
    import pandas as pd

# Sector display order for stacking (excludes Total Nonfarm)
SECTOR_STACK_ORDER: List[str] = [
    "Education & Health",
    "Leisure & Hospitality",
    "Prof & Business Svcs",
    "Government",
    "Financial Activities",
    "Construction",
    "Manufacturing",
    "Information",
]

# Color palette per sector
SECTOR_COLORS: Dict[str, str] = {
    "Education & Health": "#26C6DA",
    "Leisure & Hospitality": "#EC407A",
    "Prof & Business Svcs": "#AB47BC",
    "Government": "#78909C",
    "Financial Activities": "#4FC3F7",
    "Construction": "#FF7043",
    "Manufacturing": "#66BB6A",
    "Information": "#FFA726",
}

BAR_WIDTH = 0.7


class _MonthAxisItem(pg.AxisItem):
    """Maps integer indices to month label strings."""

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


class PayrollsChart(BaseChart):
    """Stacked bar chart of monthly sector payroll changes (MoM in thousands)."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._month_labels: List[str] = []
        self._sector_deltas: Dict[str, np.ndarray] = {}
        self._total_deltas: Optional[np.ndarray] = None
        self._n_months: int = 0
        self._bar_items: List[pg.BarGraphItem] = []
        self._legend_items: list = []
        self._total_line = None
        self._zero_line = None
        self._recession_bands: list = []
        self._show_gridlines = True
        self._show_hover_tooltip = True
        self._show_recession_shading = True
        self._legend = None

        self._setup_plots()
        self._setup_tooltip()
        self._setup_placeholder()

    def _setup_plots(self):
        self._bottom_axis = _MonthAxisItem(orientation="bottom")
        self._right_axis = DraggableAxisItem(orientation="right")
        self._right_axis.setWidth(70)

        self.plot_item = self.addPlot(
            axisItems={"bottom": self._bottom_axis, "right": self._right_axis}
        )
        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMouseEnabled(x=True, y=True)

        self.plot_item.showAxis("left", False)
        self.plot_item.showAxis("right", True)
        self.plot_item.showGrid(x=False, y=True, alpha=0.3)

    def _setup_tooltip(self):
        self._tooltip = QLabel(self)
        self._tooltip.setVisible(False)
        self._tooltip.setWordWrap(False)
        self._tooltip.setTextFormat(Qt.RichText)
        self._apply_tooltip_style()
        self.setMouseTracking(True)

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
        self._placeholder = QLabel("Loading payrolls data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        self._clear_plot()
        if self.plot_item:
            self.plot_item.clear()

    def _clear_plot(self):
        for item in self._bar_items:
            self.plot_item.removeItem(item)
        self._bar_items.clear()

        for item in self._legend_items:
            self.plot_item.removeItem(item)
        self._legend_items.clear()

        if self._total_line is not None:
            self.plot_item.removeItem(self._total_line)
            self._total_line = None

        if self._zero_line is not None:
            self.plot_item.removeItem(self._zero_line)
            self._zero_line = None

        for item in self._recession_bands:
            self.plot_item.removeItem(item)
        self._recession_bands.clear()

        if self._legend is not None:
            try:
                self._legend.clear()
                if self._legend.scene():
                    self._legend.scene().removeItem(self._legend)
                self.plot_item.legend = None
            except Exception:
                pass
            self._legend = None

        self._month_labels = []
        self._sector_deltas = {}
        self._total_deltas = None
        self._n_months = 0

    def update_data(
        self,
        payroll_levels: "Optional[pd.DataFrame]",
        usrec: "Optional[pd.Series]",
        settings: dict,
    ):
        self.setUpdatesEnabled(False)
        try:
            self._update_data_inner(payroll_levels, usrec, settings)
        finally:
            self.setUpdatesEnabled(True)

    def _update_data_inner(
        self,
        payroll_levels: "Optional[pd.DataFrame]",
        usrec: "Optional[pd.Series]",
        settings: dict,
    ):
        import pandas as pd

        self._clear_plot()

        if payroll_levels is None or payroll_levels.empty:
            self.show_placeholder("No payrolls data available.")
            return

        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._show_recession_shading = settings.get("show_recession_shading", True)

        deltas = payroll_levels.diff().dropna(how="all")
        if deltas.empty:
            self.show_placeholder("Insufficient payrolls data.")
            return

        self._placeholder.setVisible(False)

        self._n_months = len(deltas)
        self._month_labels = [dt.strftime("%b '%y") for dt in deltas.index]
        self._bottom_axis.set_labels(self._month_labels)

        dt_index = pd.DatetimeIndex(deltas.index)
        x = np.arange(self._n_months, dtype=float)

        self._sector_deltas = {}
        available_sectors = [s for s in SECTOR_STACK_ORDER if s in deltas.columns]
        for sector in available_sectors:
            self._sector_deltas[sector] = deltas[sector].values.astype(float)

        if "Total Nonfarm" in deltas.columns:
            self._total_deltas = deltas["Total Nonfarm"].values.astype(float)

        if self._show_recession_shading and usrec is not None:
            self._recession_bands = add_recession_bands(
                self.plot_item, usrec, dt_index
            )

        self._zero_line = pg.InfiniteLine(
            pos=0, angle=0, movable=False,
            pen=pg.mkPen(color=(160, 160, 160), width=1, style=Qt.DashLine)
        )
        self.plot_item.addItem(self._zero_line, ignoreBounds=True)

        pos_cumsum = np.zeros(self._n_months)
        neg_cumsum = np.zeros(self._n_months)

        for sector in available_sectors:
            vals = self._sector_deltas[sector]
            color_hex = SECTOR_COLORS.get(sector, "#888888")
            color = QColor(color_hex)
            brush = (color.red(), color.green(), color.blue(), 200)

            pos_vals = np.where(vals > 0, vals, 0.0)
            neg_vals = np.where(vals < 0, vals, 0.0)

            if np.any(pos_vals != 0):
                bar_pos = pg.BarGraphItem(
                    x=x, height=pos_vals, y0=pos_cumsum.copy(),
                    width=BAR_WIDTH, brush=pg.mkBrush(*brush), pen=pg.mkPen(None),
                )
                self.plot_item.addItem(bar_pos)
                self._bar_items.append(bar_pos)
                pos_cumsum += pos_vals

            if np.any(neg_vals != 0):
                bar_neg = pg.BarGraphItem(
                    x=x, height=neg_vals, y0=neg_cumsum.copy(),
                    width=BAR_WIDTH, brush=pg.mkBrush(*brush), pen=pg.mkPen(None),
                )
                self.plot_item.addItem(bar_neg)
                self._bar_items.append(bar_neg)
                neg_cumsum += neg_vals

        if self._total_deltas is not None:
            accent = self._get_theme_accent_color()
            pen = pg.mkPen(color=accent, width=2)
            self._total_line = self.plot_item.plot(x, self._total_deltas, pen=pen)

        self._add_legend(available_sectors)
        self._legend.setVisible(settings.get("show_legend", True))

        all_pos = pos_cumsum
        all_neg = neg_cumsum
        y_min = float(np.nanmin(all_neg)) if np.any(all_neg != 0) else 0.0
        y_max = float(np.nanmax(all_pos)) if np.any(all_pos != 0) else 0.0
        if self._total_deltas is not None:
            y_min = min(y_min, float(np.nanmin(self._total_deltas)))
            y_max = max(y_max, float(np.nanmax(self._total_deltas)))
        y_range = y_max - y_min if y_max != y_min else 100.0
        pad = y_range * 0.08
        self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)
        self.plot_item.setXRange(-0.5, self._n_months - 0.5, padding=0.01)

        self.plot_item.showGrid(x=False, y=self._show_gridlines, alpha=0.3)

    def _add_legend(self, sectors: List[str]):
        self._legend = self.plot_item.addLegend(offset=(10, 10))
        self._legend.setBrush(pg.mkBrush(color=(0, 0, 0, 120)))

        accent = self._get_theme_accent_color()
        dummy_total = self.plot_item.plot(
            [], [], pen=pg.mkPen(accent, width=2), name="Total Nonfarm"
        )
        self._legend_items.append(dummy_total)

        for sector in sectors:
            color_hex = SECTOR_COLORS.get(sector, "#888888")
            dummy = self.plot_item.plot(
                [], [], pen=pg.mkPen(color_hex, width=8), name=sector
            )
            self._legend_items.append(dummy)

    def _on_mouse_move(self, ev):
        if self._n_months == 0:
            return

        mouse_pos = ev.pos()
        scene_pos = self.mapToScene(mouse_pos)
        vb_rect = self.view_box.sceneBoundingRect()

        if not vb_rect.contains(scene_pos):
            self._tooltip.setVisible(False)
            return

        view_pos = self.view_box.mapSceneToView(scene_pos)
        idx = int(max(0, min(round(view_pos.x()), self._n_months - 1)))
        self._update_tooltip(idx, mouse_pos)

    def _on_mouse_leave(self, ev):
        self._tooltip.setVisible(False)

    def _update_tooltip(self, idx: int, mouse_pos):
        if not self._show_hover_tooltip:
            self._tooltip.setVisible(False)
            return
        if idx < 0 or idx >= self._n_months:
            self._tooltip.setVisible(False)
            return

        date_str = self._month_labels[idx] if idx < len(self._month_labels) else "?"
        total_str = ""
        if self._total_deltas is not None and idx < len(self._total_deltas):
            tv = self._total_deltas[idx]
            if not np.isnan(tv):
                sign = "+" if tv >= 0 else ""
                total_str = f"{sign}{tv:,.0f}K"

        lines = [f"<b>{date_str}</b>"]
        if total_str:
            lines[0] += f" &mdash; Total: <b>{total_str}</b>"

        sector_vals = []
        for sector in SECTOR_STACK_ORDER:
            if sector in self._sector_deltas:
                v = self._sector_deltas[sector][idx]
                if not np.isnan(v):
                    sector_vals.append((sector, v))

        sector_vals.sort(key=lambda kv: abs(kv[1]), reverse=True)

        for sector, v in sector_vals:
            color_hex = SECTOR_COLORS.get(sector, "#888888")
            sign = "+" if v >= 0 else ""
            lines.append(
                f'<span style="color:{color_hex};">\u25a0</span> '
                f'{sector:<24s} {sign}{v:,.0f}K'
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
        if self._total_line is not None:
            accent = self._get_theme_accent_color()
            self._total_line.setPen(pg.mkPen(color=accent, width=2))
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
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
