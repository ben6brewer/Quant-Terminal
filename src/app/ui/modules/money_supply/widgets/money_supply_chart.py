"""Money Supply Chart — M1 and M2 levels (trillions) or YoY% with recession shading."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

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

_M1_COLOR = "#4FC3F7"  # Light blue — distinct from theme accents


class MoneySupplyChart(BaseChart):
    """M1 + M2 chart with optional YoY% and recession shading."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._m1_values: Optional[np.ndarray] = None
        self._m2_values: Optional[np.ndarray] = None
        self._date_labels: list = []
        self._m1_line = None
        self._m2_line = None
        self._legend = None
        self._recession_bands: list = []
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._show_yoy = False

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
            f"border-radius: 4px; padding: 8px 10px; font-size: 12px;"
            f'font-family: "Menlo", "Consolas", "Courier New";'
        )

    def _setup_placeholder(self):
        self._placeholder = QLabel("Loading money supply data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #888888; background: transparent;")
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        if self.plot_item:
            self.plot_item.clear()
            self._m1_line = None
            self._m2_line = None
            self._recession_bands = []
            if self._legend:
                self._legend.clear()
            self._setup_crosshair()

    def update_data(
        self,
        supply_df: "Optional[pd.DataFrame]",
        usrec_df: "Optional[pd.DataFrame]",
        settings: dict,
    ):
        import pandas as pd

        if supply_df is None or supply_df.empty:
            self.show_placeholder("No money supply data available.")
            return

        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._show_yoy = settings.get("view_mode", "Raw") == "YoY %"
        show_m1 = settings.get("show_m1", True)
        show_m2 = settings.get("show_m2", True)
        show_recession = settings.get("show_recession_bands", True)

        if not show_m1 and not show_m2:
            self.show_placeholder("No series selected.")
            return

        # Compute YoY% if requested (pct_change periods=12 for monthly)
        if self._show_yoy:
            plot_df = supply_df.pct_change(periods=12) * 100
            plot_df = plot_df.dropna(how="all")
        else:
            plot_df = supply_df

        # Use M2 as primary index if available, else M1
        primary_col = "M2" if "M2" in plot_df.columns else "M1"
        primary = plot_df[primary_col].dropna()
        if primary.empty:
            self.show_placeholder("No data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = primary.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]

        # Extract values aligned to primary index
        self._m2_values = (
            plot_df["M2"].reindex(primary.index).values.astype(float)
            if "M2" in plot_df.columns else None
        )
        self._m1_values = (
            plot_df["M1"].reindex(primary.index).values.astype(float)
            if "M1" in plot_df.columns else None
        )

        self.plot_item.clear()
        self._m1_line = None
        self._m2_line = None
        self._recession_bands = []
        self._legend.clear()
        self._setup_crosshair()

        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)

        x = np.arange(len(self._dates))
        accent = self._get_theme_accent_color()
        all_vals = []

        # Recession bands first (behind lines)
        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(
                pd.DatetimeIndex(self._dates), method="ffill"
            ).fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        if show_m2 and self._m2_values is not None:
            self._m2_line = self.plot_item.plot(
                x, self._m2_values,
                pen=pg.mkPen(color=accent, width=2), name="M2"
            )
            self._m2_line.setClipToView(True)
            all_vals.append(self._m2_values)

        if show_m1 and self._m1_values is not None:
            self._m1_line = self.plot_item.plot(
                x, self._m1_values,
                pen=pg.mkPen(color=_M1_COLOR, width=2), name="M1"
            )
            self._m1_line.setClipToView(True)
            all_vals.append(self._m1_values)

        if all_vals:
            combined = np.concatenate([v[~np.isnan(v)] for v in all_vals if v is not None])
            if len(combined) > 0:
                y_min = float(np.nanmin(combined))
                y_max = float(np.nanmax(combined))
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
        suffix = "%" if self._show_yoy else "T"
        accent = self._get_theme_accent_color()

        if self._m2_line is not None and self._m2_values is not None and idx < len(self._m2_values):
            val = self._m2_values[idx]
            if not np.isnan(val):
                fmt = f"{val:.2f}{suffix}"
                lines.append(
                    f'<span style="color:rgb({accent[0]},{accent[1]},{accent[2]});">\u25a0</span>'
                    f" M2: {fmt}"
                )

        if self._m1_line is not None and self._m1_values is not None and idx < len(self._m1_values):
            val = self._m1_values[idx]
            if not np.isnan(val):
                fmt = f"{val:.2f}{suffix}"
                lines.append(
                    f'<span style="color:{_M1_COLOR};">\u25a0</span>'
                    f" M1: {fmt}"
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
        if self._m2_line is not None:
            accent = self._get_theme_accent_color()
            self._m2_line.setPen(pg.mkPen(color=accent, width=2))
        if self._m1_line is not None:
            self._m1_line.setPen(pg.mkPen(color=_M1_COLOR, width=2))
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
