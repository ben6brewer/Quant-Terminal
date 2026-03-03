"""Fed Balance Sheet Chart — simple total assets line OR stacked area breakdown."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.date_index_axis import DraggableIndexDateAxisItem
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem
from app.ui.modules.labor_market.utils import add_recession_bands

if TYPE_CHECKING:
    import pandas as pd

# Stacked area colors for breakdown view
_TREAS_COLOR  = "#4FC3F7"  # Light blue
_MBS_COLOR    = "#FFA726"  # Orange
_AGENCY_COLOR = "#66BB6A"  # Green
_LOANS_COLOR  = "#EF5350"  # Red
_OTHER_COLOR  = "#AB47BC"  # Purple


class FedBalanceSheetChart(BaseChart):
    """Fed Balance Sheet chart — total assets line or stacked area breakdown."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._date_labels: list = []
        # Simple view
        self._total_line = None
        # Breakdown view
        self._area_items: list = []
        self._legend = None
        self._recession_bands: list = []
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._show_breakdown = False
        # Data for tooltip
        self._total_values: Optional[np.ndarray] = None
        self._treas_values: Optional[np.ndarray] = None
        self._mbs_values: Optional[np.ndarray] = None
        self._agency_values: Optional[np.ndarray] = None
        self._loans_values: Optional[np.ndarray] = None
        self._other_values: Optional[np.ndarray] = None

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
        self._placeholder = QLabel("Loading Fed balance sheet data...", self)
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
            self._total_line = None
            self._recession_bands = []
            if self._legend:
                self._legend.clear()
            self.plot_item.clear()
            self._setup_crosshair()

    def update_data(
        self,
        bs_df: "Optional[pd.DataFrame]",
        usrec_df: "Optional[pd.DataFrame]",
        settings: dict,
    ):
        import pandas as pd

        if bs_df is None or bs_df.empty:
            self.show_placeholder("No Fed balance sheet data available.")
            return

        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._show_breakdown = settings.get("show_breakdown", False)
        show_recession = settings.get("show_recession_bands", True)
        show_treasuries = settings.get("show_treasuries", True)
        show_mbs = settings.get("show_mbs", True)
        show_agency_debt = settings.get("show_agency_debt", True)
        show_loans = settings.get("show_loans", True)
        show_other = settings.get("show_other", True)

        primary_col = "Total Assets" if "Total Assets" in bs_df.columns else bs_df.columns[0]
        primary = bs_df[primary_col].dropna()
        if primary.empty:
            self.show_placeholder("No data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = primary.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]

        self._total_values  = primary.values.astype(float)
        self._treas_values  = bs_df["Treasuries"].reindex(primary.index).values.astype(float) if "Treasuries" in bs_df.columns else None
        self._mbs_values    = bs_df["MBS"].reindex(primary.index).values.astype(float) if "MBS" in bs_df.columns else None
        self._agency_values = bs_df["Agency Debt"].reindex(primary.index).values.astype(float) if "Agency Debt" in bs_df.columns else None
        self._loans_values  = bs_df["Loans"].reindex(primary.index).values.astype(float) if "Loans" in bs_df.columns else None
        self._other_values  = bs_df["Other"].reindex(primary.index).values.astype(float) if "Other" in bs_df.columns else None

        self._clear_plot()
        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))
        accent = self._get_theme_accent_color()

        # Recession bands (behind lines/areas)
        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(dt_index, method="ffill").fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        if not self._show_breakdown:
            # Simple line view
            self._total_line = self.plot_item.plot(
                x, self._total_values,
                pen=pg.mkPen(color=accent, width=2), name="Total Assets"
            )
            self._total_line.setClipToView(True)
            y_min = float(np.nanmin(self._total_values))
            y_max = float(np.nanmax(self._total_values))
            pad = (y_max - y_min) * 0.08 if y_max != y_min else 0.5
            self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)
        else:
            # Stacked area breakdown (largest → smallest for visual clarity)
            stacks = []
            if show_treasuries and self._treas_values is not None:
                stacks.append(("Treasuries", self._treas_values, _TREAS_COLOR))
            if show_mbs and self._mbs_values is not None:
                stacks.append(("MBS", self._mbs_values, _MBS_COLOR))
            if show_agency_debt and self._agency_values is not None:
                stacks.append(("Agency Debt", self._agency_values, _AGENCY_COLOR))
            if show_loans and self._loans_values is not None:
                stacks.append(("Loans", self._loans_values, _LOANS_COLOR))
            if show_other and self._other_values is not None:
                stacks.append(("Other", self._other_values, _OTHER_COLOR))

            if not stacks:
                self.show_placeholder("No breakdown series selected.")
                return

            cumsum = np.zeros(len(x))
            for label, vals, color_hex in stacks:
                safe_vals = np.nan_to_num(vals, nan=0.0)
                color = QColor(color_hex)
                fill_brush = pg.mkBrush(color.red(), color.green(), color.blue(), 180)
                fill_pen   = pg.mkPen(color.red(), color.green(), color.blue(), 220, width=1)
                top = cumsum + safe_vals
                # Use FillBetweenItem to create stacked area
                lower_curve = self.plot_item.plot(x, cumsum, pen=pg.mkPen(None))
                upper_curve = self.plot_item.plot(x, top, pen=fill_pen, name=label)
                fill = pg.FillBetweenItem(lower_curve, upper_curve, brush=fill_brush)
                self.plot_item.addItem(fill)
                self._area_items.extend([lower_curve, upper_curve, fill])
                cumsum = top

            y_max = float(np.nanmax(cumsum)) if len(cumsum) > 0 else 1.0
            pad = y_max * 0.08
            self.plot_item.setYRange(0, y_max + pad, padding=0)

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

        if not self._show_breakdown:
            if self._total_values is not None and idx < len(self._total_values):
                val = self._total_values[idx]
                if not np.isnan(val):
                    lines.append(
                        f'<span style="color:rgb({accent[0]},{accent[1]},{accent[2]});">\u25a0</span>'
                        f" Total Assets: ${val:.2f}T"
                    )
        else:
            for label, vals, color in [
                ("Treasuries", self._treas_values, _TREAS_COLOR),
                ("MBS", self._mbs_values, _MBS_COLOR),
                ("Agency Debt", self._agency_values, _AGENCY_COLOR),
                ("Loans", self._loans_values, _LOANS_COLOR),
                ("Other", self._other_values, _OTHER_COLOR),
            ]:
                if vals is not None and idx < len(vals):
                    val = vals[idx]
                    if not np.isnan(val):
                        lines.append(
                            f'<span style="color:{color};">\u25a0</span>'
                            f" {label}: ${val:.2f}T"
                        )
            if self._total_values is not None and idx < len(self._total_values):
                total = self._total_values[idx]
                if not np.isnan(total):
                    lines.append(f"<b>Total: ${total:.2f}T</b>")

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
