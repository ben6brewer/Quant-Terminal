"""JOLTS Chart - Dual-mode: Raw multi-line or YoY% lines."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.date_index_axis import DraggableIndexDateAxisItem
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem
from app.ui.modules.labor_market.utils import add_recession_bands

if TYPE_CHECKING:
    import pandas as pd

JOLTS_COLORS: Dict[str, str] = {
    "Job Openings": "#00d4ff",
    "Hires": "#66BB6A",
    "Quits": "#FFA726",
    "Layoffs": "#EF5350",
}

JOLTS_LABELS = list(JOLTS_COLORS.keys())


class JoltsChart(BaseChart):
    """JOLTS chart — multi-line (Raw) or YoY% lines with recession shading."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._series_data: Dict[str, np.ndarray] = {}
        self._date_labels: list = []
        self._line_items: Dict[str, pg.PlotDataItem] = {}
        self._recession_bands: list = []
        self._ref_line = None
        self._legend = None
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._show_recession_shading = True
        self._visible_series: List[str] = JOLTS_LABELS
        self._view_mode = "Raw"

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
            f'font-family: "Menlo", "Consolas", "Courier New";'
        )

    def _setup_placeholder(self):
        self._placeholder = QLabel("Loading JOLTS data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 16px; color: #888888; background: transparent;"
        )
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        self._series_data = {}
        self._line_items = {}
        self._recession_bands = []
        self._ref_line = None
        if self.plot_item:
            self.plot_item.clear()
            self._setup_crosshair()

    def update_data(
        self,
        jolts_df: "Optional[pd.DataFrame]",
        usrec: "Optional[pd.Series]",
        settings: dict,
    ):
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._show_recession_shading = settings.get("show_recession_shading", True)
        self._visible_series = settings.get("jolts_series", JOLTS_LABELS)
        self._view_mode = settings.get("view_mode", "Raw")

        if self._view_mode == "YoY %":
            self._render_yoy(jolts_df, usrec, settings)
        else:
            self._render_raw(jolts_df, usrec, settings)

    # ── Raw: multi-line ───────────────────────────────────────────────────

    def _render_raw(self, jolts_df, usrec, settings):
        import pandas as pd

        if jolts_df is None or jolts_df.empty:
            self.show_placeholder("No JOLTS data available.")
            return

        available = [c for c in JOLTS_LABELS if c in jolts_df.columns]
        if not available:
            self.show_placeholder("No JOLTS series available.")
            return

        self._placeholder.setVisible(False)

        subset = jolts_df[available].dropna(how="all")
        if subset.empty:
            self.show_placeholder("Insufficient JOLTS data.")
            return

        self._dates = subset.index.values
        dt_index = pd.DatetimeIndex(self._dates)
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]
        self._series_data = {col: subset[col].values.astype(float) for col in available}

        self.plot_item.clear()
        self._line_items = {}
        self._recession_bands = []
        self._ref_line = None
        self._legend.clear()
        self._setup_crosshair()

        self._bottom_axis.set_index(dt_index)

        if self._show_recession_shading and usrec is not None:
            self._recession_bands = add_recession_bands(
                self.plot_item, usrec, dt_index
            )

        x = np.arange(len(self._dates))
        for name in available:
            if name not in self._visible_series:
                continue
            vals = self._series_data[name]
            color = JOLTS_COLORS.get(name, "#888888")
            pen = pg.mkPen(color=color, width=2)
            item = self.plot_item.plot(x, vals, pen=pen, name=name)
            item.setClipToView(True)
            self._line_items[name] = item

        all_vals = []
        for name in self._visible_series:
            if name in self._series_data:
                all_vals.extend(v for v in self._series_data[name] if not np.isnan(v))
        if all_vals:
            y_min, y_max = min(all_vals), max(all_vals)
            y_range = y_max - y_min if y_max != y_min else 1.0
            pad = y_range * 0.08
            self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)
        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)

        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )
        self._legend.setVisible(self._show_legend)

    # ── YoY %: multi-line pct_change ──────────────────────────────────────

    def _render_yoy(self, jolts_df, usrec, settings):
        import pandas as pd

        if jolts_df is None or jolts_df.empty:
            self.show_placeholder("No JOLTS data available.")
            return

        available = [c for c in JOLTS_LABELS if c in jolts_df.columns]
        visible = [c for c in available if c in self._visible_series]
        if not visible:
            self.show_placeholder("No series selected.")
            return

        # Compute YoY% for all visible series (monthly → periods=12)
        yoy_data = {}
        for col in visible:
            yoy = jolts_df[col].pct_change(periods=12) * 100
            yoy_data[col] = yoy

        yoy_df = pd.DataFrame(yoy_data).dropna(how="all")
        if yoy_df.empty:
            self.show_placeholder("Not enough data for YoY% calculation.")
            return

        self._placeholder.setVisible(False)
        self._dates = yoy_df.index.values
        dt_index = pd.DatetimeIndex(self._dates)
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]
        self._series_data = {col: yoy_df[col].values.astype(float) for col in visible if col in yoy_df.columns}

        self.plot_item.clear()
        self._line_items = {}
        self._recession_bands = []
        self._ref_line = None
        self._legend.clear()
        self._setup_crosshair()

        self._bottom_axis.set_index(dt_index)

        if self._show_recession_shading and usrec is not None:
            self._recession_bands = add_recession_bands(
                self.plot_item, usrec, dt_index
            )

        # 0% reference line
        self._ref_line = pg.InfiniteLine(
            pos=0, angle=0,
            pen=pg.mkPen(color="#888888", width=1, style=Qt.DashLine)
        )
        self.plot_item.addItem(self._ref_line)

        x = np.arange(len(self._dates))
        for name in visible:
            if name not in self._series_data:
                continue
            vals = self._series_data[name]
            color = JOLTS_COLORS.get(name, "#888888")
            pen = pg.mkPen(color=color, width=2)
            item = self.plot_item.plot(x, vals, pen=pen, name=name)
            item.setClipToView(True)
            self._line_items[name] = item

        all_vals = []
        for vals in self._series_data.values():
            all_vals.extend(v for v in vals if not np.isnan(v))
        if all_vals:
            y_min, y_max = min(all_vals), max(all_vals)
            y_range = y_max - y_min if y_max != y_min else 2.0
            pad = y_range * 0.1
            self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)
        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)

        self.plot_item.showGrid(
            x=self._show_gridlines, y=self._show_gridlines, alpha=0.3
        )
        self._legend.setVisible(self._show_legend)

    # ── Mouse interaction ─────────────────────────────────────────────────

    def _on_mouse_move(self, ev):
        if not self._series_data or self._dates is None:
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
        self._tooltip.setVisible(False)

    def _update_tooltip(self, idx: int, mouse_pos):
        if not self._show_hover_tooltip:
            self._tooltip.setVisible(False)
            return
        n = len(self._dates)
        if idx < 0 or idx >= n:
            self._tooltip.setVisible(False)
            return

        date_str = self._date_labels[idx] if idx < len(self._date_labels) else "?"
        lines = [f"<b>{date_str}</b>"]

        if self._view_mode == "YoY %":
            for name in self._visible_series:
                if name in self._series_data:
                    val = self._series_data[name][idx]
                    if not np.isnan(val):
                        color = JOLTS_COLORS.get(name, "#888888")
                        lines.append(
                            f'<span style="color:{color};">\u25a0</span> '
                            f'{name}: {val:+.1f}%'
                        )
        else:
            for name in self._visible_series:
                if name in self._series_data:
                    val = self._series_data[name][idx]
                    if not np.isnan(val):
                        color = JOLTS_COLORS.get(name, "#888888")
                        val_str = f"{val/1000:.2f}M" if val >= 1000 else f"{val:,.0f}K"
                        lines.append(
                            f'<span style="color:{color};">\u25a0</span> '
                            f'{name:<16s} {val_str}'
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
