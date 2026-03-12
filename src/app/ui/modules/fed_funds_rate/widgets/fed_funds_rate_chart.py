"""Fed Funds Rate Chart — EFFR history with optional target range band and recession shading."""

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
from app.ui.modules.labor_market.utils import add_recession_bands

if TYPE_CHECKING:
    import pandas as pd


class FedFundsRateChart(BaseChart):
    """FEDFUNDS line with optional DFEDTARL-DFEDTARU band and recession shading."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._effr_values: Optional[np.ndarray] = None
        self._lower_values: Optional[np.ndarray] = None
        self._upper_values: Optional[np.ndarray] = None
        self._date_labels: list = []
        self._effr_line = None
        self._target_band_fill = None
        self._target_lower_line = None
        self._target_upper_line = None
        self._recession_bands: list = []
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_hover_tooltip = True
        self._show_target_band = True

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
        self._placeholder = QLabel("Loading Fed funds rate data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #888888; background: transparent;")
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        if self.plot_item:
            self.plot_item.clear()
            self._effr_line = None
            self._target_band_fill = None
            self._target_lower_line = None
            self._target_upper_line = None
            self._recession_bands = []
            self._setup_crosshair()

    def update_data(
        self,
        effr_df: "Optional[pd.DataFrame]",
        usrec_df: "Optional[pd.DataFrame]",
        settings: dict,
    ):
        import pandas as pd

        if effr_df is None or effr_df.empty:
            self.show_placeholder("No Fed funds rate data available.")
            return

        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._show_target_band = settings.get("show_target_band", True)
        show_recession = settings.get("show_recession_bands", True)

        # Use FEDFUNDS as primary series
        effr_col = "Fed Funds Rate" if "Fed Funds Rate" in effr_df.columns else effr_df.columns[0]
        effr_series = effr_df[effr_col].dropna()
        if effr_series.empty:
            self.show_placeholder("No EFFR data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = effr_series.index.values
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]
        self._effr_values = effr_series.values.astype(float)

        # Extract target bounds (daily data — resample/align to monthly index for display)
        if "Lower Target" in effr_df.columns and "Upper Target" in effr_df.columns:
            self._lower_values = effr_df["Lower Target"].reindex(effr_series.index, method="ffill").values.astype(float)
            self._upper_values = effr_df["Upper Target"].reindex(effr_series.index, method="ffill").values.astype(float)
        else:
            self._lower_values = None
            self._upper_values = None

        self.plot_item.clear()
        self._effr_line = None
        self._target_band_fill = None
        self._target_lower_line = None
        self._target_upper_line = None
        self._recession_bands = []
        self._setup_crosshair()

        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)
        x = np.arange(len(self._dates))
        accent = self._get_theme_accent_color()

        # Recession bands first (behind lines)
        if show_recession and usrec_df is not None and not usrec_df.empty:
            usrec_series = usrec_df["USREC"].reindex(dt_index, method="ffill").fillna(0)
            self._recession_bands = add_recession_bands(self.plot_item, usrec_series, dt_index)

        # Target range band (shaded fill between lower and upper, post-2008)
        if (self._show_target_band and self._lower_values is not None
                and self._upper_values is not None):
            # Only draw where both bounds are non-NaN
            mask = ~(np.isnan(self._lower_values) | np.isnan(self._upper_values))
            if np.any(mask):
                band_color = QColor(accent[0], accent[1], accent[2])
                fill_brush = pg.mkBrush(band_color.red(), band_color.green(), band_color.blue(), 40)
                band_pen   = pg.mkPen(band_color.red(), band_color.green(), band_color.blue(), 80, width=1)

                lower_curve = self.plot_item.plot(
                    x, np.where(mask, self._lower_values, np.nan),
                    pen=band_pen
                )
                upper_curve = self.plot_item.plot(
                    x, np.where(mask, self._upper_values, np.nan),
                    pen=band_pen
                )
                fill = pg.FillBetweenItem(lower_curve, upper_curve, brush=fill_brush)
                self.plot_item.addItem(fill)
                self._target_lower_line = lower_curve
                self._target_upper_line = upper_curve
                self._target_band_fill = fill

        # EFFR line on top
        self._effr_line = self.plot_item.plot(
            x, self._effr_values,
            pen=pg.mkPen(color=accent, width=2.5), name="Fed Funds Rate"
        )
        self._effr_line.setClipToView(True)

        valid = self._effr_values[~np.isnan(self._effr_values)]
        if len(valid) > 0:
            y_min = float(np.nanmin(valid))
            y_max = float(np.nanmax(valid))
            y_range = y_max - y_min if y_max != y_min else 1.0
            pad = y_range * 0.1
            self.plot_item.setYRange(max(0, y_min - pad), y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._dates) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)

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

        if self._effr_values is not None and idx < len(self._effr_values):
            val = self._effr_values[idx]
            if not np.isnan(val):
                lines.append(
                    f'<span style="color:rgb({accent[0]},{accent[1]},{accent[2]});">\u25a0</span>'
                    f" EFFR: {val:.2f}%"
                )

        if (self._lower_values is not None and self._upper_values is not None
                and idx < len(self._lower_values)):
            lo = self._lower_values[idx]
            hi = self._upper_values[idx]
            if not (np.isnan(lo) or np.isnan(hi)):
                lines.append(f' Target: {lo:.2f}%–{hi:.2f}%')

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
        if self._effr_line is not None:
            accent = self._get_theme_accent_color()
            self._effr_line.setPen(pg.mkPen(color=accent, width=2.5))
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
