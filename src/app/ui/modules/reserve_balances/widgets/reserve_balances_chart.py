"""Reserve Balances Chart — bank reserves at Fed with optional Total Assets overlay."""

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

_OVERLAY_COLOR = "#FFA726"  # Orange for Total Assets overlay


class ReserveBalancesChart(BaseChart):
    """Reserve Balances (primary) with optional dashed Total Assets overlay."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._reserves_values: Optional[np.ndarray] = None
        self._total_assets_values: Optional[np.ndarray] = None
        self._date_labels: list = []
        self._reserves_line = None
        self._overlay_line = None
        self._legend = None
        self._recession_bands: list = []
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._show_total_assets_overlay = False

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
        self._placeholder = QLabel("Loading reserve balances data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #888888; background: transparent;")
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        if self.plot_item:
            self.plot_item.clear()
            self._reserves_line = None
            self._overlay_line = None
            self._recession_bands = []
            if self._legend:
                self._legend.clear()
            self._setup_crosshair()

    def update_data(
        self,
        reserves_df: "Optional[pd.DataFrame]",
        balance_sheet_df: "Optional[pd.DataFrame]",
        usrec_df: "Optional[pd.DataFrame]",
        settings: dict,
    ):
        import pandas as pd

        if reserves_df is None or reserves_df.empty:
            self.show_placeholder("No reserve balances data available.")
            return

        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._show_total_assets_overlay = settings.get("show_total_assets_overlay", False)
        show_recession = settings.get("show_recession_bands", True)

        primary_col = "Reserve Balances" if "Reserve Balances" in reserves_df.columns else reserves_df.columns[0]
        primary = reserves_df[primary_col].dropna()
        if primary.empty:
            self.show_placeholder("No data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = primary.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]
        self._reserves_values = primary.values.astype(float)

        # Total assets overlay (from balance_sheet_df)
        self._total_assets_values = None
        if (self._show_total_assets_overlay and balance_sheet_df is not None
                and not balance_sheet_df.empty and "Total Assets" in balance_sheet_df.columns):
            self._total_assets_values = (
                balance_sheet_df["Total Assets"]
                .reindex(primary.index, method="ffill")
                .values.astype(float)
            )

        self.plot_item.clear()
        self._reserves_line = None
        self._overlay_line = None
        self._recession_bands = []
        self._legend.clear()
        self._setup_crosshair()

        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))
        accent = self._get_theme_accent_color()

        # Recession bands first
        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(dt_index, method="ffill").fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        # Dashed overlay (Total Assets) drawn first so reserves line appears on top
        if self._total_assets_values is not None:
            self._overlay_line = self.plot_item.plot(
                x, self._total_assets_values,
                pen=pg.mkPen(color=_OVERLAY_COLOR, width=1.5, style=Qt.DashLine),
                name="Total Assets"
            )
            self._overlay_line.setClipToView(True)

        # Primary reserves line
        self._reserves_line = self.plot_item.plot(
            x, self._reserves_values,
            pen=pg.mkPen(color=accent, width=2), name="Reserve Balances"
        )
        self._reserves_line.setClipToView(True)

        all_vals = [self._reserves_values]
        if self._total_assets_values is not None:
            all_vals.append(self._total_assets_values)
        combined = np.concatenate([v[~np.isnan(v)] for v in all_vals])
        if len(combined) > 0:
            y_min = max(0.0, float(np.nanmin(combined)))
            y_max = float(np.nanmax(combined))
            pad = (y_max - y_min) * 0.08 if y_max != y_min else 0.5
            self.plot_item.setYRange(y_min, y_max + pad, padding=0)

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

        if self._reserves_values is not None and idx < len(self._reserves_values):
            val = self._reserves_values[idx]
            if not np.isnan(val):
                lines.append(
                    f'<span style="color:rgb({accent[0]},{accent[1]},{accent[2]});">\u25a0</span>'
                    f" Reserves: ${val:.2f}T"
                )

        if self._total_assets_values is not None and idx < len(self._total_assets_values):
            val = self._total_assets_values[idx]
            if not np.isnan(val):
                lines.append(
                    f'<span style="color:{_OVERLAY_COLOR};">\u25a0</span>'
                    f" Total Assets: ${val:.2f}T"
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
        if self._reserves_line is not None:
            accent = self._get_theme_accent_color()
            self._reserves_line.setPen(pg.mkPen(color=accent, width=2))
        if self._overlay_line is not None:
            self._overlay_line.setPen(pg.mkPen(color=_OVERLAY_COLOR, width=1.5, style=Qt.DashLine))
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
